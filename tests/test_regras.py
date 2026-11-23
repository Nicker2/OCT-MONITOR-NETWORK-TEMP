"""Testes das regras puras do monitor (sem abrir janelas nem precisar do hardware).

O script principal baixa/abre o Core Temp ao ser importado, entao aqui as
funcoes sao extraidas do arquivo com `ast` e executadas isoladamente.

Rodar:  python -m unittest discover -s tests
"""
import ast
import os
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "oct-monitor-cpu-network-temp.py")
NOMES = {"pasta_do_programa", "classificar_temperatura", "TEMP_AVISO_C", "TEMP_CRITICA_C"}


def carregar_regras():
    with open(SCRIPT, encoding="utf-8") as f:
        arvore = ast.parse(f.read())
    nos = []
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef) and no.name in NOMES:
            nos.append(no)
        elif isinstance(no, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in NOMES for t in no.targets
        ):
            nos.append(no)
    ns = {"os": os, "sys": sys, "__file__": os.path.abspath(SCRIPT)}
    exec(compile(ast.Module(body=nos, type_ignores=[]), SCRIPT, "exec"), ns)
    return ns


R = carregar_regras()


class TestFaixasTemperatura(unittest.TestCase):
    def test_faixas(self):
        casos = {
            0: "normal", 55: "normal", 75.9: "normal", 75.99: "normal",
            76: "warn", 76.0: "warn", 82: "warn", 87: "warn",
            87.5: "warn", 87.99: "warn",  # antes caiam no buraco (normal)
            88: "crit", 88.0: "crit", 92: "crit", 120: "crit",
        }
        for temp, esperado in casos.items():
            with self.subTest(temp=temp):
                self.assertEqual(R["classificar_temperatura"](temp), esperado)

    def test_sem_buraco(self):
        # varre 0..120 em passos de 0,01 e confere que a sequencia so sobe
        ordem = {"normal": 0, "warn": 1, "crit": 2}
        anterior = 0
        for i in range(0, 12001):
            atual = ordem[R["classificar_temperatura"](i / 100)]
            self.assertGreaterEqual(atual, anterior, f"regrediu em {i / 100}")
            anterior = atual


class TestPastaDoPrograma(unittest.TestCase):
    def test_exe_usa_pasta_do_executavel(self):
        exe = os.path.join(os.sep, "MonitorOCT", "MonitorOCT.exe")
        pasta = R["pasta_do_programa"](frozen=True, executable=exe)
        self.assertEqual(pasta, os.path.dirname(os.path.abspath(exe)))
        self.assertNotIn("_MEI", pasta)

    def test_python_usa_pasta_do_script(self):
        script = os.path.join(os.sep, "proj", "oct-monitor-cpu-network-temp.py")
        pasta = R["pasta_do_programa"](frozen=False, script=script)
        self.assertEqual(pasta, os.path.dirname(os.path.abspath(script)))


if __name__ == "__main__":
    unittest.main()
