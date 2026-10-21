"""Whole-source loader. No normal app package initializer or model rewriting."""
import ast
import builtins
import hashlib
import importlib.util
import importlib.machinery
from pathlib import Path
import sys
import types

class ExactFinder:
    def __init__(self, inventory):
        self.modules = {}
        for filename, sha in {**inventory['runtime'], **inventory['libraries']}.items():
            p = Path(filename)
            normalized = str(p).replace('\\', '/')
            if '/site-packages/' in normalized:
                relative = normalized.split('/site-packages/', 1)[1]
            elif '/Lib/' in normalized:
                relative = normalized.split('/Lib/', 1)[1]
            elif '/DLLs/' in normalized:
                relative = normalized.split('/DLLs/', 1)[1]
            else:
                continue
            if p.suffix.lower() not in {'.py', '.pyd'} or '.dist-info/' in relative:
                continue
            package = relative.endswith('/__init__.py')
            name = relative[:-12] if package else relative.rsplit('.', 1)[0]
            if p.suffix.lower() == '.pyd':
                name = name.split('.', 1)[0]
            self.modules[name.replace('/', '.')] = (p, sha, package)
        self.namespaces = {}
        for fullname, (path, sha, package) in self.modules.items():
            parts = fullname.split('.')
            for length in range(1, len(parts)):
                prefix = '.'.join(parts[:length])
                if prefix not in self.modules:
                    ancestor = path.parent
                    for _ in range(len(parts) - length - (0 if package else 1)):
                        ancestor = ancestor.parent
                    self.namespaces.setdefault(prefix, set()).add(str(ancestor))

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app', 'config', 'testing_safety'}:
            raise ImportError('Normal app initializer blocked: ' + fullname)
        item = self.modules.get(fullname)
        if item is None:
            locations = self.namespaces.get(fullname)
            if locations:
                spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
                spec.submodule_search_locations = sorted(locations)
                return spec
            return None
        p, sha, package = item
        if p.suffix.lower() == '.pyd':
            if hashlib.sha256(p.read_bytes()).hexdigest() != sha:
                raise PermissionError('Native source hash drift: ' + str(p))
            return importlib.util.spec_from_file_location(fullname, str(p))
        return importlib.util.spec_from_file_location(fullname, str(p), loader=ExactCode(p, sha),
                   submodule_search_locations=[str(p.parent)] if package else None)

class ExactCode:
    def __init__(self, path, sha):
        self.path, self.sha = path, sha
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        source = self.path.read_bytes()
        if hashlib.sha256(source).hexdigest() != self.sha:
            raise PermissionError('Exact source hash drift: ' + str(self.path))
        exec(compile(source, str(self.path), 'exec'), module.__dict__)

def load_models(boundary):
    finder = ExactFinder(boundary.inventory)
    sys.meta_path[:] = [importlib.machinery.BuiltinImporter, importlib.machinery.FrozenImporter, finder]
    from flask_sqlalchemy import SQLAlchemy
    from sqlalchemy.orm import configure_mappers
    if boundary.denials:
        raise PermissionError('Unexpected library read denial: ' + repr(boundary.denials))
    db = SQLAlchemy()
    repo = Path('C:/Users/aproa/momoai_web')
    original_import = builtins.__import__
    db_module = types.SimpleNamespace(db=db)
    def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'app.models' and tuple(fromlist) == ('db',) and level == 0:
            return db_module
        if name.split('.')[0] in {'app', 'config', 'testing_safety'}:
            raise ImportError('Model import outside exact db resolver: ' + name)
        if name.split('.')[0] not in {'datetime', 'uuid', 'flask_login', 'werkzeug'}:
            raise ImportError('Unexpected model import: ' + name)
        return original_import(name, globals, locals, fromlist, level)
    classes = {}
    hashes = {}
    for relative, expected in boundary.gate['models'].items():
        path = repo / relative
        source = path.read_bytes()
        sha = hashlib.sha256(source).hexdigest()
        if sha != expected['sha256']:
            raise PermissionError('Model source hash mismatch: ' + relative)
        tree = ast.parse(source, filename=str(path))
        names = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        if names != [c['name'] for c in expected['classes']]:
            raise PermissionError('Model class inventory drift: ' + relative)
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            if relative == 'app/models/essay.py' and isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {'ESSAY_TYPES', 'ESSAY_TYPE_DEFAULT'}:
                ast.literal_eval(node.value)
                continue
            raise PermissionError('Unapproved model top-level statement: ' + relative)
        module_name = '_br_actual_' + path.stem
        module = types.ModuleType(module_name)
        module.__file__ = str(path)
        module.__dict__['__builtins__'] = {**vars(builtins), '__import__': restricted_import}
        sys.modules[module_name] = module
        # Whole original byte source is compiled: methods, defaults and relationships unchanged.
        exec(compile(source, str(path), 'exec'), module.__dict__)
        classes.update({name: module.__dict__[name] for name in names})
        hashes[relative] = sha
    configure_mappers()
    if boundary.denials:
        raise PermissionError('Swallowed exact-read denial: ' + repr(boundary.denials))
    return {'model_count': len(classes), 'table_names': sorted(db.metadata.tables), 'configured': True,
            'db': db, 'classes': classes, 'source_hashes': hashes}
