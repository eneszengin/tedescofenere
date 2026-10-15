#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Geri doldurma — Mackolik arsiv, takim sezon sayfasi.

Bu kaynak Fenerbahce'nin bir sezondaki TUM maclarini kulvar kulvar veriyor:
Super Lig, Turkiye Kupasi, Super Kupa, Avrupa kupalari ve elemeler.
Her macin detay baglantisi da sayfada var; goller ve kartlar orada.
Hazirlik maclari atlanir.

Kullanim:
    python scripts/mackolik_doldur.py --dene     # tek sezon, ekrana basar
    python scripts/mackolik_doldur.py --kuru     # hepsi, dosya yazmaz
    python scripts/mackolik_doldur.py            # veriler.json uretir

Once --dene calistir ve listeyi kontrol et.
"""

import argparse
import datetime as dt
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Windows konsolu cp1252 kullanir ve Turkce karakterlerde coker.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

KALIP = "https://arsiv.mackolik.com/Team/Default.aspx?id=2&season={sezon}"
MAC_KOKU = "https://arsiv.mackolik.com/Mac/"
CIKTI = Path(__file__).resolve().parent.parent / "veriler.json"
BIZ = "Fenerbahçe"

BASLIKLAR = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# Sayfadaki kulvar basliklari -> sitedeki kulvar kodu
KULVARLAR = [
    ("Türkiye Süper Kupa", "SK"),
    ("Süper Kupa", "SK"),
    ("Türkiye Kupa", "TK"),
    ("UEFA Şampiyonlar Ligi", "SAM"),
    ("UEFA Avrupa Ligi", "AL"),
    ("UEFA Konferans Ligi", "KON"),
    ("UEFA Kupası", "AL"),
    ("Türkiye Süper Lig", "SL"),
    ("Trendyol Süper Lig", "SL"),
    ("Süper Lig", "SL"),
    ("Hazırlık", "ATLA"),
]
# Avrupa'da eleme turlari lig asamasindan ayri sayilir
ELEME = re.compile(r"eleme|play\s*-?\s*off|ön eleme", re.I)

AD_DUZELT = {
    "Karagümrük": "Fatih Karagümrük",
    "B. Yeniçarşı": "Beyoğlu Yeni Çarşı",
    "Not.Forest": "Nottingham Forest",
    "V.Plzen": "Viktoria Plzen",
    "Gornik Zabrze": "Górnik Zabrze",
    "Atletico Madrid": "Atlético Madrid",
    "LASK Linz": "LASK",
    "Slavia Prag": "Slavia Prag",
    "Shakhtar": "Shakhtar Donetsk",
    "Amed SK": "Amed SFK",
}

SEZONLAR = [f"{y}/{y+1}" for y in range(2010, 2026)]   # 2010/2011 ... 2025/2026

DONEMLER = [
    {"id": "kocaman-2010",  "ad": "Aykut Kocaman",  "donem": "2010–13",
     "bas": "2010-07-01", "bit": "2013-06-30"},
    {"id": "yanal-2013",    "ad": "Ersun Yanal",    "donem": "2013–14",
     "bas": "2013-07-01", "bit": "2014-06-30"},
    {"id": "kartal-2014",   "ad": "İsmail Kartal",  "donem": "2014–15",
     "bas": "2014-07-01", "bit": "2015-06-30"},
    {"id": "pereira-2015",  "ad": "Vítor Pereira",  "donem": "2015–16",
     "bas": "2015-07-01", "bit": "2016-06-30"},
    {"id": "advocaat-2016", "ad": "Dick Advocaat",  "donem": "2016–17",
     "bas": "2016-07-01", "bit": "2017-06-30"},
    {"id": "kocaman-2017",  "ad": "Aykut Kocaman",  "donem": "2017–18",
     "bas": "2017-07-01", "bit": "2018-06-30"},
    {"id": "cocu-2018",     "ad": "Phillip Cocu",   "donem": "2018",
     "bas": "2018-07-01", "bit": "2018-10-28"},
    {"id": "yanal-2018",    "ad": "Ersun Yanal",    "donem": "2018–20",
     "bas": "2019-01-01", "bit": "2020-03-15"},
    {"id": "bulut-2020",    "ad": "Erol Bulut",     "donem": "2020–21",
     "bas": "2020-07-21", "bit": "2021-03-24"},
    {"id": "pereira-2021",  "ad": "Vítor Pereira",  "donem": "2021–22",
     "bas": "2021-07-01", "bit": "2021-12-21"},
    {"id": "kartal-2022",   "ad": "İsmail Kartal",  "donem": "2021–22",
     "bas": "2022-01-13", "bit": "2022-06-30"},
    {"id": "jesus-2022",    "ad": "Jorge Jesus",    "donem": "2022–23",
     "bas": "2022-07-01", "bit": "2023-06-30"},
    {"id": "kartal-2023",   "ad": "İsmail Kartal",  "donem": "2023–24",
     "bas": "2023-07-01", "bit": "2024-06-30"},
    {"id": "mourinho-2024", "ad": "José Mourinho",  "donem": "2024–25",
     "bas": "2024-07-01", "bit": "2025-08-29"},
]

# «MAC:id:skor» isaretcisi: baglantilari metin akisinda korumak icin
ISARET = re.compile(r"«M(\d+):([^»]*)»")
MAC_DESENI = re.compile(
    r"(\d{1,2}\.\d{2}\.\d{4})\s+(.{2,40}?)\s*«M(\d+):([^»]*)»\s*(.{2,40}?)\s+"
    r"(?:\d+-\d+|\d{1,2}\.\d{2}\.\d{4}|$)"
)


def temizle(ad):
    ad = re.sub(r"\s+", " ", ad).strip(" .,-—–")
    return AD_DUZELT.get(ad, ad)


def kulvar_kodu(baslik, altbaslik):
    for anahtar, kod in KULVARLAR:
        if anahtar.lower() in baslik.lower():
            if kod in ("SAM", "AL", "KON") and ELEME.search(altbaslik or ""):
                return "ELE" if kod == "SAM" else kod
            return kod
    return None


def sayfayi_al(url, deneme=4):
    """Arsiv sunucusu arada 502/500 veriyor; sabirla tekrar dene."""
    bekleme = [5, 15, 30, 60]
    son_hata = None
    for i in range(deneme):
        try:
            y = requests.get(url, headers=BASLIKLAR, timeout=45)
            y.raise_for_status()
            return y.text
        except requests.HTTPError as e:
            kod = e.response.status_code if e.response is not None else 0
            son_hata = e
            if kod not in (500, 502, 503, 504):
                raise
        except requests.RequestException as e:
            son_hata = e
        if i < deneme - 1:
            s = bekleme[i]
            print(f"(sunucu hatasi, {s} sn sonra tekrar)", end=" ", flush=True)
            time.sleep(s)
    raise son_hata


def sezonu_cek(sezon):
    corba = BeautifulSoup(sayfayi_al(KALIP.format(sezon=sezon)), "html.parser")

    # Mac baglantilarini metne goster: «M{id}:{skor}»
    kimlikler = {}
    for bag in corba.find_all("a", href=re.compile(r"/Mac/\d+")):
        e = re.search(r"/Mac/(\d+)", bag["href"])
        if not e:
            continue
        kimlikler[e.group(1)] = True
        bag.string = f"«M{e.group(1)}:{bag.get_text(strip=True)}»"

    metin = re.sub(r"\s+", " ", corba.get_text(" "))

    # Kulvar basliklarinin metindeki yerlerini bul
    isaretler = []
    for anahtar, _ in KULVARLAR:
        for e in re.finditer(re.escape(anahtar), metin):
            isaretler.append((e.start(), anahtar))
    # Alt basliklar (eleme turu vb.)
    for e in re.finditer(r"(Eleme Turu|Play\s*-?\s*Off|Lig Aşaması|Ön Eleme)", metin):
        isaretler.append((e.start(), "@" + e.group(1)))
    isaretler.sort()

    def kulvar_bul(konum):
        baslik = altbaslik = ""
        for yer, ad in isaretler:
            if yer > konum:
                break
            if ad.startswith("@"):
                altbaslik = ad[1:]
            else:
                baslik, altbaslik = ad, ""
        return kulvar_kodu(baslik, altbaslik)

    maclar, atlanan = [], 0
    for e in MAC_DESENI.finditer(metin):
        tarih_ham, ev, mac_id, skor_ham, dep = e.groups()
        kod = kulvar_bul(e.start())
        if kod is None or kod == "ATLA":
            atlanan += 1
            continue

        g, a, yil = re.match(r"(\d{1,2})\.(\d{2})\.(\d{4})", tarih_ham).groups()
        tarih = f"{yil}-{a}-{int(g):02d}"

        ev, dep = temizle(ev), temizle(dep)
        if BIZ not in (ev, dep):
            continue

        s = re.match(r"(\d+)\s*-\s*(\d+)", skor_ham.strip())
        if not s:
            continue                        # oynanmamis mac
        g1, g2 = int(s.group(1)), int(s.group(2))
        bizEv = (ev == BIZ)

        maclar.append([
            tarih, kod, "İ" if bizEv else "D",
            dep if bizEv else ev,
            f"{g1}-{g2}" if bizEv else f"{g2}-{g1}",
            mac_id,
        ])

    benzersiz = {m[5]: m for m in maclar}
    return sorted(benzersiz.values(), key=lambda m: m[0]), atlanan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dene", action="store_true")
    ap.add_argument("--kuru", action="store_true")
    args = ap.parse_args()

    if args.dene:
        s = SEZONLAR[0]
        print(f"Deneme: {s}\n{KALIP.format(sezon=s)}\n")
        maclar, atlanan = sezonu_cek(s)
        print(f"{len(maclar)} resmi mac bulundu, {atlanan} hazirlik/diger atlandi\n")
        for m in maclar:
            print("  ", m[0], m[1].ljust(4), m[2], m[3].ljust(20), m[4].ljust(6),
                  MAC_KOKU + m[5])
        return

    tum = []
    for s in SEZONLAR:
        print(f"-> {s}", end=" ", flush=True)
        try:
            maclar, _ = sezonu_cek(s)
        except Exception as e:
            raise SystemExit(f"\nHATA: {s} cekilemedi: {e}")
        print(f"{len(maclar)} mac")
        if len(maclar) < 30:
            raise SystemExit(
                f"HATA: {s} icin yalnizca {len(maclar)} mac bulundu. "
                f"--dene ile kontrol et. Dosya yazilmadi."
            )
        tum.extend(maclar)
        time.sleep(3)

    tum.sort(key=lambda m: m[0])
    print(f"\nToplam: {len(tum)} mac\n")
    print(f"{'Donem':22} {'Yil':10} {'mac':>5}  {'G-B-M':>10}  {'ort':>5}")
    print("-" * 60)

    cikti = []
    for d in DONEMLER:
        maclar = [m for m in tum if d["bas"] <= m[0] <= d["bit"]]
        g = b = 0
        for m in maclar:
            x, y = map(int, m[4].split("-"))
            g += x > y
            b += x == y
        k = len(maclar) - g - b
        ort = (g * 3 + b) / len(maclar) if maclar else 0
        print(f"{d['ad']:22} {d['donem']:10} {len(maclar):5}  "
              f"{f'{g}-{b}-{k}':>10}  {ort:5.2f}")
        cikti.append({"id": d["id"], "ad": d["ad"], "donem": d["donem"],
                      "maclar": maclar})

    if args.kuru:
        print("\n[kuru calisma] veriler.json yazilmadi.")
        return

    io.open(CIKTI, "w", encoding="utf-8").write(json.dumps(
        {"uretim": dt.date.today().isoformat(), "kaynak": "mackolik-arsiv",
         "macKoku": MAC_KOKU, "donemler": cikti}, ensure_ascii=False, indent=1))
    print(f"\nveriler.json yazildi ({CIKTI.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
