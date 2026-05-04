diff --git a/apps/contas/tests.py b/apps/contas/tests.py
index b334eb019b28f82c7b5df4d26ca86195699a381b..faa1bde522318226c7a270b73f784eb463526604 100644
--- a/apps/contas/tests.py
+++ b/apps/contas/tests.py
@@ -1,4 +1,22 @@
-﻿from django.test import TestCase
+from pathlib import Path
 
-# Create your tests here.
+from django.template import TemplateSyntaxError
+from django.template.loader import get_template
+from django.test import SimpleTestCase
 
+
+class PortalTemplateTests(SimpleTestCase):
+    def test_portal_template_compiles_without_duplicate_sidebar_block(self):
+        try:
+            get_template('contas/portal.html')
+        except TemplateSyntaxError as exc:
+            self.fail(f'portal template should compile without syntax errors: {exc}')
+
+    def test_portal_template_has_single_sidebar_block_declaration(self):
+        template_path = Path(__file__).resolve().parent / 'templates' / 'contas' / 'portal.html'
+        source = template_path.read_text(encoding='utf-8')
+        self.assertLessEqual(source.count('{% block sidebar %}'), 1)
+
+    def test_root_route_renders_successfully(self):
+        response = self.client.get('/')
+        self.assertEqual(response.status_code, 200)
