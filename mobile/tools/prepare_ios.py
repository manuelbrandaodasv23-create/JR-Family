#!/usr/bin/env python3
"""Configura o projeto iOS gerado pelo Flutter para o JR Family.

Execute dentro de mobile:
  flutter create --platforms=ios --org com.jrfamily --project-name jr_family .
  python3 tools/prepare_ios.py

Nao gera certificados nem instala no iPhone; a assinatura e feita no Xcode.
"""
from pathlib import Path
import plistlib
import re

ROOT = Path(__file__).resolve().parent.parent
IOS = ROOT / "ios"
INFO = IOS / "Runner" / "Info.plist"
PODFILE = IOS / "Podfile"
PROJECT = IOS / "Runner.xcodeproj" / "project.pbxproj"
MINIMUM_IOS = "15.0"
BUNDLE_ID = "com.jrfamily.app"

for required in (INFO, PODFILE, PROJECT):
    if not required.is_file():
        raise SystemExit(
            f"Arquivo {required} inexistente. Primeiro rode flutter create --platforms=ios ."
        )

with INFO.open("rb") as f:
    info = plistlib.load(f)
info["CFBundleDisplayName"] = "JR Family"
info["NSLocationWhenInUseUsageDescription"] = (
    "O JR Family usa a localizacao, com sua autorizacao, para compartilhar "
    "sua posicao com integrantes autorizados da sua familia."
)
info["NSLocationAlwaysAndWhenInUseUsageDescription"] = (
    "Se voce ativar o compartilhamento continuo, o JR Family podera "
    "atualizar sua localizacao em segundo plano, inclusive com o app fechado "
    "na tela. Voce pode desativar o compartilhamento a qualquer momento."
)
modes = list(info.get("UIBackgroundModes", []))
if "location" not in modes:
    modes.append("location")
info["UIBackgroundModes"] = modes
with INFO.open("wb") as f:
    plistlib.dump(info, f, sort_keys=False)

podfile = PODFILE.read_text(encoding="utf-8")
pattern = r"(?m)^[ \t]*#?[ \t]*platform[ \t]+:ios,[ \t]*['\"][0-9.]+['\"].*$"
replacement = f"platform :ios, '{MINIMUM_IOS}'"
podfile, count = re.subn(pattern, replacement, podfile, count=1)
if count == 0:
    podfile = replacement + "\n" + podfile
PODFILE.write_text(podfile, encoding="utf-8")

project = PROJECT.read_text(encoding="utf-8")
project, target_changes = re.subn(
    r"IPHONEOS_DEPLOYMENT_TARGET = [0-9.]+;",
    f"IPHONEOS_DEPLOYMENT_TARGET = {MINIMUM_IOS};",
    project,
)
if target_changes == 0:
    raise SystemExit("Nao foi possivel ajustar IPHONEOS_DEPLOYMENT_TARGET no Xcode.")

def replace_bundle(match: re.Match[str]) -> str:
    old = match.group(2).strip('"')
    suffix = ".RunnerTests" if "RunnerTests" in old else ""
    return match.group(1) + BUNDLE_ID + suffix + match.group(3)

project, id_changes = re.subn(
    r"(PRODUCT_BUNDLE_IDENTIFIER = )([^;]+)(;)",
    replace_bundle,
    project,
)
if id_changes == 0:
    raise SystemExit("Nao foi possivel ajustar PRODUCT_BUNDLE_IDENTIFIER no Xcode.")
PROJECT.write_text(project, encoding="utf-8")

print(
    f"JR Family iOS configurado: {BUNDLE_ID}, iOS {MINIMUM_IOS}+, "
    "permissoes de localizacao e atualizacao visivel em segundo plano."
)
print("Apple ID gratuito: assinatura automatica (Personal Team) deve ser feita no Xcode.")
print("Firebase/FCM nao esta configurado; nao ative notificacoes push sem credenciais.")
