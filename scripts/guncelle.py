#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fikstur guncelleyici — API-Football surumu.

Neden API: onceki surum worldfootball sayfalarini tariyordu ve o site sunucu
IP'lerinden gelen istekleri 403 ile reddediyor. GitHub Actions da bir sunucu
oldugu icin otomasyon hic calismadi. API-Football otomatik erisim icin
tasarlanmis; ucretsiz plani gunde 100 istek veriyor, bu betik calisma basina
yaklasik 4 istek harciyor.

Gerekli: API_FOOTBALL_KEY ortam degiskeni.
  - GitHub'da: repo > Settings > Secrets and variables > Actions > New secret
  - Windows'ta: set API_FOOTBALL_KEY=xxx
  - mac/Linux:  export API_FOOTBALL_KEY=xxx

Kullanim:
    python scripts/guncelle.py --kuru    # yazmaz, sadece raporlar
    python scripts/guncelle.py           # index.html'i gunceller

Davranis: mevcut satirlarin yalnizca skorunu tazeler; rakip adlari ve mac
raporu linkleri korunur. API'de olup bizde olmayan mac varsa (ornegin kupa
kurasi cekilince) tarih sirasina eklenir, o maclarin raporu linki olmaz.
"""

import argparse
import datetime as dt
import io
import os
import re
import time
import unicodedata
from pathlib import Path

import requests

API = "https://v3.football.api-sports.io"
HEDEF = Path(__file__).resolve().parent.parent / "index.html"
ANAHTAR = os.environ.get("API_FOOTBALL_KEY", "").strip()

# API'deki turnuva adi -> sitedeki kulvar kodu.
# Ad uzerinden esleriz; turnuva kimlikleri sezonlar arasi degisebiliyor.
KULVAR_ADI = {
    "super lig": "SL",
    "serie a": "SL_A",
    "uefa champions league": "SAM",
    "uefa europa league": "AL",
    "turkish cup": "TK",
    "super cup": "SK",
}

# Sampiyonlar Ligi eleme turlari ayri kulvar sayilir (lig asamasi degil).
ELEME_TURU = re.compile(r"qualifying|play-?off|preliminary", re.I)

AD_DUZELT = {
    "Besiktas": "Beşiktaş", "Trabzonspor": "Trabzonspor", "Galatasaray": "Galatasaray",
    "Istanbul Basaksehir": "Başakşehir", "Basaksehir": "Başakşehir",
    "Caykur Rizespor": "Çaykur Rizespor", "Rizespor": "Çaykur Rizespor",
    "Genclerbirligi": "Gençlerbirliği", "Goztepe": "Göztepe",
    "Kasimpasa": "Kasımpaşa", "Eyupspor": "Eyüpspor",
    "Fatih Karagumruk": "Fatih Karagümrük", "Karagumruk": "Fatih Karagümrük",
    "Corum": "Çorum FK", "Corum FK": "Çorum FK",
    "Gazisehir Gaziantep": "Gaziantep FK", "Gaziantep FK": "Gaziantep FK",
    "Erzurum BB": "Erzurumspor FK", "Erzurumspor": "Erzurumspor FK",
    "Amed Sportif": "Amed SFK", "Kocaelispor": "Kocaelispor",
    "AS Roma": "Roma", "AC Milan": "Milan", "Olympique Lyonnais": "Lyon",
    "Slavia Praha": "Slavia Prag", "Gornik Zabrze": "Górnik Zabrze",
    "Atletico Madrid": "Atlético Madrid",
}

BITMIS = {"FT", "AET", "PEN"}

DONEMLER = [
    {"id": "fb-simdi", "takim": "Fenerbahce", "takim_id": None,
     "sezon": 2026, "en_az": 40},
    {"id": "ted-bol",  "takim": "Bologna",    "takim_id": None,
     "sezon": 2026, "en_az": 34},
]


def cagir(yol, **parametre):
    if not ANAHTAR:
        raise SystemExit(
            "HATA: API_FOOTBALL_KEY tanimli degil.\n"
            "api-football.com uzerinden ucretsiz bir anahtar al, sonra\n"
            "repo > Settings > Secrets and variables > Actions bolumune\n"
            "API_FOOTBALL_KEY adiyla ekle."
        )
    y = requests.get(f"{API}/{yol}", params=parametre,
                     headers={"x-apisports-key": ANAHTAR}, timeout=30)
    y.raise_for_status()
    veri = y.json()
    if veri.get("errors"):
        raise SystemExit(f"HATA: API hatasi -> {veri['errors']}")
    return veri.get("response", [])


def takim_id_bul(ad):
    sonuc = cagir("teams", search=ad)
    if not sonuc:
        raise SystemExit(f"HATA: '{ad}' takimi bulunamadi.")
    t = sonuc[0]["team"]
    print(f"   takim: {t['name']} (id {t['id']})")
    return t["id"]


def kulvar_bul(lig):
    ad = unicodedata.normalize("NFKD", lig["name"]) \
        .encode("ascii", "ignore").decode().lower()
    tur = lig.get("round") or ""
    if "champions league" in ad and ELEME_TURU.search(tur):
        return "ELE"
    for anahtar, kod in KULVAR_ADI.items():
        if anahtar in ad:
            return kod
    return None


def maclari_getir(donem):
    ham = cagir("fixtures", team=donem["takim_id"], season=donem["sezon"])
    maclar, bilinmeyen = [], set()

    for f in ham:
        kulvar = kulvar_bul(f["league"])
        if not kulvar:
            bilinmeyen.add(f["league"]["name"])
            continue

        ev = f["teams"]["home"]["id"] == donem["takim_id"]
        rakip_ham = f["teams"]["away" if ev else "home"]["name"]

        skor = None
        if f["fixture"]["status"]["short"] in BITMIS:
            bizim = f["goals"]["home" if ev else "away"]
            onun = f["goals"]["away" if ev else "home"]
            if bizim is not None and onun is not None:
                skor = f"{bizim}-{onun}"

        maclar.append({
            "tarih": f["fixture"]["date"][:10],
            "kulvar": kulvar,
            "yer": "İ" if ev else "D",
            "rakip": AD_DUZELT.get(rakip_ham, rakip_ham),
            "skor": skor,
        })

    if bilinmeyen:
        print("   UYARI: taninmayan turnuva ->", ", ".join(sorted(bilinmeyen)))
        print("   KULVAR_ADI sozlugune eklenmesi gerekebilir.")
    return sorted(maclar, key=lambda m: m["tarih"])


def mevcut_satirlar(icerik, donem_id):
    """index.html icindeki satirlari okur; link ve elle duzeltilmis adi korumak icin."""
    blok = re.search(r'id:"%s",.*?maclar:\[(.*?)\n    \]' % re.escape(donem_id),
                     icerik, re.S)
    if not blok:
        raise SystemExit(f"HATA: '{donem_id}' blogu index.html icinde yok.")
    satirlar = {}
    desen = (r'\["(\d{4}-\d\d-\d\d)","(\w+)","(.)","([^"]*)",'
             r'(null|"[\d-]+")(?:,"([^"]*)")?\]')
    for e in re.finditer(desen, blok.group(1)):
        tarih, kulvar, yer, rakip, skor, link = e.groups()
        satirlar[tarih] = {
            "tarih": tarih, "kulvar": kulvar, "yer": yer, "rakip": rakip,
            "skor": None if skor == "null" else skor.strip('"'),
            "link": link,
        }
    return satirlar


def satir_yaz(m):
    skor = f'"{m["skor"]}"' if m.get("skor") else "null"
    link = f',"{m["link"]}"' if m.get("link") else ""
    return (f'      ["{m["tarih"]}","{m["kulvar"]}","{m["yer"]}",'
            f'"{m["rakip"]}",{skor}{link}]')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true",
                    help="index.html'e yazmadan neyin degisecegini goster")
    args = ap.parse_args()

    icerik = io.open(HEDEF, encoding="utf-8").read()
    orijinal, rapor = icerik, []

    for donem in DONEMLER:
        print(f"-> {donem['id']}")
        if not donem["takim_id"]:
            donem["takim_id"] = takim_id_bul(donem["takim"])

        api_maclari = maclari_getir(donem)
        if len(api_maclari) < donem["en_az"]:
            raise SystemExit(
                f"HATA: {donem['id']} icin {len(api_maclari)} mac dondu, "
                f"en az {donem['en_az']} bekleniyordu. Sezon numarasi yanlis "
                f"olabilir ya da API kapsami degismis. index.html'e dokunulmadi."
            )

        birlesik = mevcut_satirlar(icerik, donem["id"])

        for m in api_maclari:
            var = birlesik.get(m["tarih"])
            if var:
                if m["skor"] and var["skor"] != m["skor"]:
                    rapor.append(f"   {m['tarih']}  {var['rakip']}: "
                                 f"{var['skor'] or '—'} -> {m['skor']}")
                    var["skor"] = m["skor"]
            else:
                rapor.append(f"   + YENI MAC  {m['tarih']}  {m['rakip']} "
                             f"({m['kulvar']})")
                birlesik[m["tarih"]] = m

        sirali = [birlesik[t] for t in sorted(birlesik)]
        blok = "maclar:[\n" + ",\n".join(satir_yaz(m) for m in sirali) + "\n    ]"
        icerik, adet = re.subn(
            r'(id:"%s",.*?)maclar:\[.*?\n    \]' % re.escape(donem["id"]),
            lambda e: e.group(1) + blok, icerik, flags=re.S)
        if adet != 1:
            raise SystemExit(f"HATA: '{donem['id']}' blogu yazilamadi.")
        print(f"   {len(sirali)} mac islendi")
        time.sleep(1)

    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    b = dt.date.today()
    icerik = re.sub(r'const SON_GUNCELLEME = "[^"]*";',
                    f'const SON_GUNCELLEME = "{b.day} {aylar[b.month-1]} {b.year}";',
                    icerik)

    if rapor:
        print("\nDegisiklikler:")
        print("\n".join(rapor))
    else:
        print("\nYeni sonuc yok.")

    if icerik == orijinal:
        print("index.html degismedi.")
        return
    if args.kuru:
        print("\n[kuru calisma] index.html'e yazilmadi.")
        return

    io.open(HEDEF, "w", encoding="utf-8").write(icerik)
    print("index.html guncellendi.")


if __name__ == "__main__":
    main()
