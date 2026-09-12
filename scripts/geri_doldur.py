#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tek seferlik geri doldurma betigi.

2010-11'den 2025-26'ya kadar Fenerbahce'nin tum maclarini kaynaktan ceker,
teknik direktor devir tarihlerine gore boler ve veriler.json dosyasini uretir.
Site bu dosyayi yalnizca kullanici eski bir donem sectiginde yukler.

Kullanim:
    python3 scripts/geri_doldur.py --kuru    # yazmaz, sadece raporlar
    python3 scripts/geri_doldur.py           # veriler.json olusturur

ONEMLI: Once mutlaka --kuru ile calistir ve "beklenen" sutunuyla "bulunan"
sutununun tuttugunu kontrol et. Tutmuyorsa DONEMLER icindeki tarihler
yanlistir; duzeltip tekrar dene. Tarihler duzelmeden dosyayi uretme.
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

KOK = "https://www.worldfootball.net"
TAKIM = "/teams/te735/fenerbahce"
CIKTI = Path(__file__).resolve().parent.parent / "veriler.json"

# match-report linkindeki turnuva kodu -> sitedeki kulvar kodu
KULVAR_KODU = {
    "co116": "SL",     # Super Lig
    "co130": "TK",     # Turkiye Kupasi
    "co120": "SK",     # Super Kupa
    "co19":  "SAM",    # Sampiyonlar Ligi
    "co562": "ELE",    # Sampiyonlar Ligi elemeleri
    "co132": "AL",     # Avrupa Ligi
    "co563": "AL",     # Avrupa Ligi elemeleri
}
ATLA = {"co4135"}      # hazirlik maclari

# Kaynaktaki yazimlari siteye uydur. Derbi suzgeci bu adlara bakiyor,
# Besiktas/Galatasaray/Trabzonspor satirlari kritik.
AD_DUZELT = {
    "Besiktas": "Beşiktaş",
    "Besiktas JK": "Beşiktaş",
    "Trabzonspor": "Trabzonspor",
    "Galatasaray": "Galatasaray",
    "Galatasaray SK": "Galatasaray",
    "Basaksehir FK": "Başakşehir",
    "Istanbul Basaksehir": "Başakşehir",
    "Istanbul BB": "Başakşehir",
    "Caykur Rizespor": "Çaykur Rizespor",
    "Genclerbirligi": "Gençlerbirliği",
    "Genclerbirligi Ankara": "Gençlerbirliği",
    "Goztepe": "Göztepe",
    "Goeztepe": "Göztepe",
    "Kasimpasa": "Kasımpaşa",
    "Kasimpasa SK": "Kasımpaşa",
    "Eyuepspor": "Eyüpspor",
    "Fatih Karagumruk": "Fatih Karagümrük",
    "Fatih Karaguemruek": "Fatih Karagümrük",
    "Buyuksehir Belediyespor": "Başakşehir",
    "Mersin Idman Yurdu": "Mersin İdmanyurdu",
    "Akhisar Belediyespor": "Akhisarspor",
    "Osmanlispor": "Osmanlıspor",
    "Denizlispor": "Denizlispor",
    "Sivasspor": "Sivasspor",
    "Alanyaspor": "Alanyaspor",
    "Konyaspor": "Konyaspor",
    "Kayserispor": "Kayserispor",
    "Antalyaspor": "Antalyaspor",
    "Samsunspor": "Samsunspor",
    "Kocaelispor": "Kocaelispor",
    "Erzurumspor FK": "Erzurumspor FK",
    "Gaziantep FK": "Gaziantep FK",
    "Corum FK": "Çorum FK",
    "Amed SFK": "Amed SFK",
}

# Teknik direktor donemleri. Tarihler [baslangic, bitis] araligi kapsayicidir.
# "beklenen" degeri, sitedeki teknik direktor tablosundan gelir; dogrulama icin.
# Vekil donemler simdilik disarida (site tablosunda da yoklar).
DONEMLER = [
    {"id": "kocaman-2010",  "ad": "Aykut Kocaman",    "donem": "2010–13",
     "bas": "2010-07-01", "bit": "2013-06-30", "beklenen": 151},
    {"id": "yanal-2013",    "ad": "Ersun Yanal",      "donem": "2013–14",
     "bas": "2013-07-01", "bit": "2014-06-30", "beklenen": 40},
    {"id": "kartal-2014",   "ad": "İsmail Kartal",    "donem": "2014–15",
     "bas": "2014-07-01", "bit": "2015-06-30", "beklenen": 46},
    {"id": "pereira-2015",  "ad": "Vítor Pereira",    "donem": "2015–16",
     "bas": "2015-07-01", "bit": "2016-06-30", "beklenen": 61},
    {"id": "advocaat-2016", "ad": "Dick Advocaat",    "donem": "2016–17",
     "bas": "2016-07-01", "bit": "2017-06-30", "beklenen": 55},
    {"id": "kocaman-2017",  "ad": "Aykut Kocaman",    "donem": "2017–18",
     "bas": "2017-07-01", "bit": "2018-06-30", "beklenen": 46},
    {"id": "cocu-2018",     "ad": "Phillip Cocu",     "donem": "2018",
     "bas": "2018-07-01", "bit": "2018-10-28", "beklenen": 15},
    {"id": "yanal-2018",    "ad": "Ersun Yanal",      "donem": "2018–20",
     "bas": "2018-11-01", "bit": "2020-07-20", "beklenen": 56},
    {"id": "bulut-2020",    "ad": "Erol Bulut",       "donem": "2020–21",
     "bas": "2020-07-21", "bit": "2021-03-24", "beklenen": 34},
    {"id": "pereira-2021",  "ad": "Vítor Pereira",    "donem": "2021–22",
     "bas": "2021-07-01", "bit": "2021-12-21", "beklenen": 25},
    {"id": "kartal-2022",   "ad": "İsmail Kartal",    "donem": "2021–22",
     "bas": "2022-01-13", "bit": "2022-06-30", "beklenen": 21},
    {"id": "jesus-2022",    "ad": "Jorge Jesus",      "donem": "2022–23",
     "bas": "2022-07-01", "bit": "2023-06-30", "beklenen": 53},
    {"id": "kartal-2023",   "ad": "İsmail Kartal",    "donem": "2023–24",
     "bas": "2023-07-01", "bit": "2024-06-30", "beklenen": 58},
    {"id": "mourinho-2024", "ad": "José Mourinho",    "donem": "2024–25",
     "bas": "2024-07-01", "bit": "2025-08-29", "beklenen": 62},
]

SEZONLAR = [(y, y + 1) for y in range(2010, 2026)]   # 2010-11 ... 2025-26


BASLIKLAR = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


def cek(url):
    try:
        y = requests.get(url, headers=BASLIKLAR, timeout=30)
        y.raise_for_status()
        return y.text
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            raise SystemExit(
                "HATA: Kaynak site istegi reddetti (403).\n"
                "Bu genellikle sunucu IP'lerinden gelen otomatik istekleri\n"
                "engelledigi anlamina gelir. GitHub Actions da bir sunucudur.\n"
                "Betigi kendi bilgisayarindan calistirmayi dene:\n"
                "  pip install requests beautifulsoup4\n"
                "  python3 scripts/geri_doldur.py --kuru\n"
                "Orada da 403 aliyorsan site otomatik erisime kapali demektir;\n"
                "zorlamak yerine baska bir kaynak bulmak gerekir."
            )
        raise


def maclari_ayikla(html, bilinmeyen):
    corba = BeautifulSoup(html, "html.parser")
    maclar = []

    for satir in corba.select("tr"):
        hucreler = satir.find_all("td")
        if len(hucreler) < 5:
            continue

        t = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})",
                         hucreler[0].get_text(strip=True))
        if not t:
            continue
        g, a, y = t.groups()
        iso = f"{y}-{a}-{g}"

        rapor = satir.find("a", href=re.compile(r"/match-report/"))
        if not rapor:
            continue
        yol = re.search(r"/match-report/(.+?)/?$", rapor["href"]).group(1) + "/"
        turnuva = yol.split("/")[0]
        if turnuva in ATLA:
            continue
        kulvar = KULVAR_KODU.get(turnuva)
        if not kulvar:
            bilinmeyen.add(turnuva)
            continue

        yer = None
        for hucre in hucreler:
            metin = hucre.get_text(strip=True)
            if metin in ("H", "A"):
                yer = "İ" if metin == "H" else "D"
                break
        if yer is None:
            continue

        rakip = None
        for hucre in hucreler:
            bag = hucre.find("a", href=re.compile(r"/teams/"))
            if bag and bag.get_text(strip=True):
                rakip = bag.get_text(strip=True)
        if not rakip:
            continue
        rakip = AD_DUZELT.get(rakip, rakip)

        ham = rapor.get_text(strip=True)
        if not re.fullmatch(r"\d+:\d+", ham):
            continue                      # oynanmamis mac: gecmise gerek yok
        skor = ham.replace(":", "-")

        maclar.append([iso, kulvar, yer, rakip, skor, yol])

    return maclar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true",
                    help="veriler.json yazmadan raporla")
    args = ap.parse_args()

    tum, bilinmeyen = {}, set()

    for bas, bit in SEZONLAR:
        url = f"{KOK}{TAKIM}/vs{bas}-{bit}/all-matches/"
        print(f"-> {bas}-{bit} taraniyor")
        try:
            maclar = maclari_ayikla(cek(url), bilinmeyen)
        except Exception as e:
            raise SystemExit(f"HATA: {bas}-{bit} cekilemedi: {e}")
        if len(maclar) < 20:
            print(f"   UYARI: yalnizca {len(maclar)} mac bulundu, sayfa yapisi "
                  f"farkli olabilir")
        for m in maclar:
            tum[(m[0], m[5])] = m         # tarih + link ile tekille
        print(f"   {len(maclar)} mac")
        time.sleep(2)

    if bilinmeyen:
        print("\nUYARI: taninmayan turnuva kodlari atlandi ->",
              ", ".join(sorted(bilinmeyen)))
        print("Bunlari KULVAR_KODU sozlugune ekleyip tekrar calistir.")

    hepsi = sorted(tum.values(), key=lambda m: m[0])
    print(f"\nToplam benzersiz mac: {len(hepsi)}")

    # --- donemlere bol ve dogrula ---
    print(f"\n{'Donem':22} {'Yil':10} {'bulunan':>8} {'beklenen':>9}  durum")
    print("-" * 62)

    cikti, sorunlu = [], 0
    for d in DONEMLER:
        maclar = [m for m in hepsi if d["bas"] <= m[0] <= d["bit"]]
        fark = len(maclar) - d["beklenen"]
        durum = "tamam" if fark == 0 else f"FARK {fark:+d}"
        if fark != 0:
            sorunlu += 1
        print(f"{d['ad']:22} {d['donem']:10} {len(maclar):8} "
              f"{d['beklenen']:9}  {durum}")
        cikti.append({"id": d["id"], "ad": d["ad"], "donem": d["donem"],
                      "maclar": maclar})

    if sorunlu:
        print(f"\n{sorunlu} donemde sayi tutmuyor. DONEMLER icindeki 'bas'/'bit' "
              f"tarihlerini duzeltip tekrar calistir.")
        print("Dosya yazilmadi.")
        return

    if args.kuru:
        print("\n[kuru calisma] veriler.json yazilmadi.")
        return

    io.open(CIKTI, "w", encoding="utf-8").write(json.dumps(
        {"uretim": dt.date.today().isoformat(), "donemler": cikti},
        ensure_ascii=False, indent=1))
    boyut = CIKTI.stat().st_size // 1024
    print(f"\nveriler.json yazildi ({boyut} KB, {len(cikti)} donem)")


if __name__ == "__main__":
    main()
