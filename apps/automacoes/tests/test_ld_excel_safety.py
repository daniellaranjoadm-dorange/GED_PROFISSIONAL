import ast
import hashlib
import os
import shutil
import tempfile
import traceback
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

SOURCE=Path(__file__).with_name('atualizar_ld_projeto_basico.py')
if not SOURCE.exists():
    SOURCE=Path(__file__).parents[1]/'services'/'atualizar_ld_projeto_basico.py'
TREE=ast.parse(SOURCE.read_text(encoding='utf-8'))
NAMES={'PlanilhaEmUsoError','_arquivo_exclusivo','_verificar_disponibilidade_ld','_assinatura_ld','_restaurar_ld_se_inalterada','processar'}

def namespace():
    ns=dict(os=os,Path=Path,hashlib=hashlib,shutil=shutil,contextmanager=contextmanager,datetime=datetime,traceback=traceback)
    exec(compile(ast.Module(body=[n for n in TREE.body if getattr(n,'name',None) in NAMES],type_ignores=[]),str(SOURCE),'exec'),ns)
    return ns

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root=Path(self.tmp.name)
        self.ns=namespace()
        self.main=self.root/'main.xlsm'; self.main.write_bytes(b'original-main')
        self.second=self.root/'second.xlsx'; self.second.write_bytes(b'original-second')
    def tearDown(self): self.tmp.cleanup()
    def test_real_windows_lock_rejected(self):
        with self.ns['_arquivo_exclusivo'](self.second):
            with self.assertRaises(self.ns['PlanilhaEmUsoError']):
                self.ns['_verificar_disponibilidade_ld']([self.main,self.second])
        self.assertEqual(self.second.read_bytes(),b'original-second')
    def test_excel_owner_file_rejected(self):
        self.second.with_name('~$'+self.second.name).touch()
        with self.assertRaises(self.ns['PlanilhaEmUsoError']):
            self.ns['_verificar_disponibilidade_ld']([self.main,self.second])
    def test_restore_only_unchanged_and_unlocked(self):
        backup=self.root/'backup'; backup.write_bytes(b'backup')
        fingerprint=self.ns['_assinatura_ld'](self.main)
        with self.ns['_arquivo_exclusivo'](self.main):
            with self.assertRaises(self.ns['PlanilhaEmUsoError']):
                self.ns['_restaurar_ld_se_inalterada'](self.main,backup,fingerprint)
        self.main.write_bytes(b'other-user')
        with self.assertRaises(RuntimeError):
            self.ns['_restaurar_ld_se_inalterada'](self.main,backup,fingerprint)
        self.assertEqual(self.main.read_bytes(),b'other-user')
        fingerprint=self.ns['_assinatura_ld'](self.main)
        self.ns['_restaurar_ld_se_inalterada'](self.main,backup,fingerprint)
        self.assertEqual(self.main.read_bytes(),b'backup')
    def prepare_process(self,readonly=False,processing_error=False,import_error=False):
        ns=self.ns
        process=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='processar')
        for node in ast.walk(process):
            if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load) and node.id not in ns and node.id not in dir(__builtins__): ns[node.id]=Mock()
        ns.update(PLANILHA=str(self.main),PLANILHA_MARENOVA_EXECUTIVO=str(self.second),PASTA_LOGS=str(self.root/'logs'),PASTA_BACKUPS=str(self.root/'backups'))
        ns['indexar_engenharia_info']=Mock(return_value={})
        ns['backup_arquivo']=Mock(side_effect=lambda p:self.backup(p))
        self.books=[]
        def open_book(path,**kwargs):
            book=Mock(); book.api.ReadOnly=readonly and path==str(self.second)
            book.save.side_effect=lambda:Path(path).write_bytes(b'saved-ged')
            self.books.append(book)
            return book
        app=Mock(); app.books.open.side_effect=open_book
        @contextmanager
        def session():
            try: yield app
            finally:
                for book in self.books: book.close()
        ns['_sessao_excel_ld']=session
        def process_sheet(*args,**kwargs):
            self.assertEqual(len(self.books),2)
            if processing_error: raise RuntimeError('OLE test')
        ns['processar_aba']=Mock(side_effect=process_sheet)
        ns['importar_ld_banco']=Mock(side_effect=RuntimeError('database test') if import_error else None)
        return ns
    def backup(self,path):
        target=self.root/(Path(path).name+'.bak')
        shutil.copy2(path,target)
        return str(target)
    def test_second_readonly_cancels_before_any_processing_or_save(self):
        ns=self.prepare_process(readonly=True)
        with self.assertRaises(ns['PlanilhaEmUsoError']): ns['processar']()
        ns['processar_aba'].assert_not_called()
        for book in self.books: book.save.assert_not_called()
        self.assertEqual(self.main.read_bytes(),b'original-main')
    def test_ole_before_save_never_restores(self):
        ns=self.prepare_process(processing_error=True)
        ns['_restaurar_ld_se_inalterada']=Mock()
        with self.assertRaisesRegex(RuntimeError,'OLE test'): ns['processar']()
        ns['_restaurar_ld_se_inalterada'].assert_not_called()
        for book in self.books: book.save.assert_not_called()
        self.assertEqual(self.main.read_bytes(),b'original-main')
    def test_database_error_restores_confirmed_saves(self):
        ns=self.prepare_process(import_error=True)
        with self.assertRaisesRegex(RuntimeError,'database test'): ns['processar']()
        for book in self.books:
            book.save.assert_called_once(); book.close.assert_called_once()
        self.assertEqual(self.main.read_bytes(),b'original-main')
        self.assertEqual(self.second.read_bytes(),b'original-second')

    def test_failed_second_save_does_not_overwrite_unconfirmed_file(self):
        ns=self.prepare_process(import_error=True)
        original_process=ns['processar_aba'].side_effect
        def processing(*args,**kwargs):
            original_process(*args,**kwargs)
            self.books[1].save.side_effect=RuntimeError('save failed')
        ns['processar_aba'].side_effect=processing
        with self.assertRaisesRegex(RuntimeError,'save failed'): ns['processar']()
        ns['importar_ld_banco'].assert_not_called()
        self.assertEqual(self.main.read_bytes(),b'original-main')
        self.assertEqual(self.second.read_bytes(),b'original-second')

if __name__=='__main__': unittest.main(verbosity=2)
