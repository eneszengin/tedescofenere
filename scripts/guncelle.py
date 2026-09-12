#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
index.html icindeki fikstur verisini kaynaktan cekip gunceller.

Kullanim:
    python3 scripts/guncelle.py --kuru     # hicbir sey yazmaz, sadece raporlar
    python3 scripts/guncelle.py            # index.html'i gunceller

Mantik: guncellenecek her donem icin kaynaktaki sezon sayfasi taranir,
maclar yeniden insa edilir ve index.html icindeki ilgili "maclar:[...]"
blogu degistirilir. Kapanmis donemler (Tedesco/Fenerbahce, Gole) hic
dokunulmaz - onlar sabit tarihsel veridir.
"""

import argparse
import datetime as dt
import io
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

KOK = "https://www.worldfootball.net"
HEDEF = Path(__file__).resolve().parent.parent / "index.html"

# match-report linkindeki turnuva kodu -> sitedeki kulvar kodu
KULVAR_KODU = {
    "co116": "SL",     # Super Lig
    "co111": "SL_A",   # Serie A
    "co132": "AL",     # Avrupa Ligi
    "co130": "TK",     # Turkiye Kupasi
    "co120": "SK",     # Super Kupa
    "co19":  "SAM",    # Sampiyonlar Ligi
    "co562": "ELE",    # SL elemeleri
}
ATLA = {"co4135"}  # hazirlik maclari

# Guncellenecek donemler. Kapanmis donemler listede yok, bilerek.
DONEMLER = [
    {
        "id": "fb-simdi",
        "url": f"{KOK}/teams/te735/fenerbahce/all-matches/",
        "baslangic": "2026-07-01",
        "bitis": None,      # teknik direktor degisirse buraya tarih yaz
        "en_az": 40,        # bu sayidan az mac bulunursa is hatayla durur
    },
    {
        "id": "ted-bol",
        "url": f"{KOK}/teams/te249/bologna-fc/all-matches/",
        "baslangic": "2026-07-01",
        "bitis": None,
        "en_az": 34,
    },
]


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
                "  python3 scripts/guncelle.py --kuru\n"
                "Orada da 403 aliyorsan site otomatik erisime kapali demektir;\n"
                "zorlamak yerine baska bir kaynak bulmak gerekir."
            )
        raise


def maclari_ayikla(html):
    """Sezon sayfasindaki satirlardan mac listesi cikarir."""
    corba = BeautifulSoup(html, "html.parser")
    maclar = []
    bilinmeyen = set()

    for satir in corba.select("tr"):
        hucreler = satir.find_all("td")
        if len(hucreler) < 5:
            continue

        metin = hucreler[0].get_text(strip=True)
        tarih = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", metin)
        if not tarih:
            continue
        g, a, y = tarih.groups()
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
            # Yeni bir turnuva cikmis olabilir (or. Konferans Ligi).
            # Maci atlarız ama sessiz kalmayız; loga yazilir.
            bilinmeyen.add(turnuva)
            continue

        # ic saha / deplasman: tek harfi "H" ya da "A" olan hucre
        yer = None
        for h in hucreler:
            t = h.get_text(strip=True)
            if t in ("H", "A"):
                yer = "İ" if t == "H" else "D"
                break
        if yer is None:
            continue

        rakip = None
        for h in hucreler:
            bag = h.find("a", href=re.compile(r"/teams/"))
            if bag and bag.get_text(strip=True):
                rakip = bag.get_text(strip=True)
        if not rakip:
            continue

        # skor: rapor linklerinin ilki. oynanmadiysa "-:-" gelir.
        skor = None
        ham = rapor.get_text(strip=True)
        if re.fullmatch(r"\d+:\d+", ham):
            skor = ham.replace(":", "-")

        maclar.append({
            "tarih": iso, "kulvar": kulvar, "yer": yer,
            "rakip": rakip, "skor": skor, "link": yol,
        })

    # ayni mac birden fazla satirda gecebilir; tarihe gore tekille
    if bilinmeyen:
        print("   UYARI: taninmayan turnuva kodu atlandi ->",
              ", ".join(sorted(bilinmeyen)),
              "\n   (KULVAR_KODU ve KULVAR sozlugune eklenmesi gerekebilir)")

    tekil = {}
    for m in maclar:
        tekil[(m["tarih"], m["link"])] = m
    return sorted(tekil.values(), key=lambda m: m["tarih"])


def satir_yaz(m):
    skor = f'"{m["skor"]}"' if m["skor"] else "null"
    rakip = m["rakip"].replace('"', "'")
    return (f'      ["{m["tarih"]}","{m["kulvar"]}","{m["yer"]}",'
            f'"{rakip}",{skor},"{m["link"]}"]')


def blogu_degistir(icerik, donem_id, maclar):
    kalip = re.compile(r'(id:"%s",.*?)maclar:\[.*?\n    \]' % re.escape(donem_id), re.S)
    yeni_blok = "maclar:[\n" + ",\n".join(satir_yaz(m) for m in maclar) + "\n    ]"
    icerik, adet = kalip.subn(lambda e: e.group(1) + yeni_blok, icerik)
    if adet != 1:
        raise SystemExit(f"HATA: '{donem_id}' blogu index.html icinde bulunamadi.")
    return icerik


def mevcut_adlar(icerik, donem_id):
    """Link -> elle duzeltilmis rakip adi. Kaynagin yazimi bunlari ezmesin."""
    blok = re.search(r'id:"%s",.*?maclar:\[(.*?)\n    \]' % re.escape(donem_id),
                     icerik, re.S)
    if not blok:
        return {}
    bulunan = re.findall(r'"([^"]+)",(?:null|"[\d-]+"),"([^"]+)"\]', blok.group(1))
    return {link: ad for ad, link in bulunan}


def mevcut_skorlar(icerik, donem_id):
    """Guncelleme oncesi durumu, degisikligi raporlayabilmek icin."""
    blok = re.search(r'id:"%s",.*?maclar:\[(.*?)\n    \]' % re.escape(donem_id),
                     icerik, re.S)
    if not blok:
        return {}
    bulunan = re.findall(r'\["(\d{4}-\d\d-\d\d)","\w+",".","[^"]*",(null|"[\d-]+")',
                         blok.group(1))
    return {t: s for t, s in bulunan}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true",
                    help="dosyaya yazmadan neyin degisecegini goster")
    args = ap.parse_args()

    icerik = io.open(HEDEF, encoding="utf-8").read()
    orijinal = icerik
    rapor = []

    for donem in DONEMLER:
        print(f"-> {donem['id']} taraniyor: {donem['url']}")
        try:
            maclar = maclari_ayikla(cek(donem["url"]))
        except Exception as e:
            raise SystemExit(f"HATA: {donem['id']} cekilemedi/ayiklanamadi: {e}")

        maclar = [m for m in maclar if m["tarih"] >= donem["baslangic"]]
        if donem["bitis"]:
            maclar = [m for m in maclar if m["tarih"] <= donem["bitis"]]

        # Guvenlik kontrolu: kaynak yapisi degisirse betik sessizce
        # veriyi silmesin, gurultuyle dursun.
        if len(maclar) < donem["en_az"]:
            raise SystemExit(
                f"HATA: {donem['id']} icin sadece {len(maclar)} mac bulundu, "
                f"en az {donem['en_az']} bekleniyordu. Kaynak sayfanin yapisi "
                f"degismis olabilir. index.html'e dokunulmadi."
            )

        # Sitede elle duzeltilmis rakip adlarini koru
        adlar = mevcut_adlar(icerik, donem["id"])
        for m in maclar:
            if m["link"] in adlar:
                m["rakip"] = adlar[m["link"]]

        onceki = mevcut_skorlar(icerik, donem["id"])
        for m in maclar:
            if m["tarih"] not in onceki:
                rapor.append(f"   + YENI MAC  {m['tarih']}  {m['rakip']} "
                             f"({m['kulvar']})")
                continue
            eski = onceki[m["tarih"]]
            yeni = f'"{m["skor"]}"' if m["skor"] else "null"
            if eski != yeni:
                rapor.append(f"   {m['tarih']}  {m['rakip']}: "
                             f"{eski.strip(chr(34)) or '—'} -> {m['skor'] or '—'}")

        icerik = blogu_degistir(icerik, donem["id"], maclar)
        print(f"   {len(maclar)} mac islendi")
        time.sleep(2)  # kaynaga nazik davran

    # "Son guncelleme" tarihini yenile
    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    bugun = dt.date.today()
    icerik = re.sub(r'const SON_GUNCELLEME = "[^"]*";',
                    f'const SON_GUNCELLEME = "{bugun.day} {aylar[bugun.month-1]} {bugun.year}";',
                    icerik)

    if rapor:
        print("\nDegisen sonuclar:")
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
