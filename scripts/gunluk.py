#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gunluk skor guncelleyici — Mackolik arsiv, guncel sezon takim sayfasi.

Her gun calisir. Yaptigi is:
  1. index.html icindeki guncel donem (fb-simdi) satirlarindan, tarihi gecmis
     ama skoru hala null olanlari bulur.
  2. Bekleyen mac yoksa hicbir seye dokunmaz, cikar. Bos commit atmaz.
  3. Bekleyen varsa Mackolik'in guncel sezon sayfasini tarar, skorlari alir.
  4. Skorlari TIRNAK ICINDE yazar, teknik direktor karnesini (mac sayisi ve
     puan ortalamasi) fikstürden yeniden hesaplar, son guncelleme tarihini
     o gune ceker.
  5. Yazmadan once dosyayi dogrular. Dogrulama kalirsa dosyaya dokunmaz.

Kullanim:
    python scripts/gunluk.py --kuru    # neyin degisecegini gosterir, yazmaz
    python scripts/gunluk.py           # index.html'i gunceller

Guvenlik frenleri:
  - Var olan bir skoru asla ezmez, yalnizca null olani doldurur.
  - Kaynaktan beklenenden az mac donerse yazmaz, hata verir.
  - Skorlar tirnaksiz yazilamaz; yazim sonrasi tarama bunu kontrol eder.
  - Teknik direktor degisirse uyarir ama karne satirinin adini kendi
     kafasina gore degistirmez.
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

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HEDEF = Path(__file__).resolve().parent.parent / "index.html"
# Fiksturde olmayan oynanmis mac bulunursa buraya yazilir. Is akisi bu dosyayi
# gorurse commit'ten SONRA isi kirmizi yakar; GitHub boylece e-posta atar.
# Commit'lenmez, repoya girmez.
ISARET_DOSYASI = Path(__file__).resolve().parent.parent / ".yeni-mac-uyarisi"
DONEM_ID = "fb-simdi"
BIZ = "Fenerbahçe"
KALIP = "https://arsiv.mackolik.com/Team/Default.aspx?id=2&season={sezon}"

# Kaynaktan bu sayinin altinda mac donerse sayfa yapisi degismis demektir.
EN_AZ_MAC = 20

BASLIKLAR = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

KULVARLAR = [
    ("Türkiye Süper Kupa", "SK"), ("Süper Kupa", "SK"),
    ("Türkiye Kupa", "TK"),
    ("UEFA Şampiyonlar Ligi", "SAM"), ("UEFA Avrupa Ligi", "AL"),
    ("UEFA Konferans Ligi", "KON"), ("UEFA Kupası", "AL"),
    ("Türkiye Süper Lig", "SL"), ("Trendyol Süper Lig", "SL"), ("Süper Lig", "SL"),
    ("Hazırlık", "ATLA"),
]
ELEME = re.compile(r"eleme|play\s*-?\s*off|ön eleme", re.I)

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

MAC_DESENI = re.compile(
    r"(\d{1,2}\.\d{2}\.\d{4})\s+(.{2,40}?)\s*«M(\d+):([^»]*)»\s*(.{2,40}?)\s+"
    r"(?:\d+-\d+|\d{1,2}\.\d{2}\.\d{4}|$)"
)

SATIR_DESENI = re.compile(
    r'\["(\d{4}-\d\d-\d\d)","(\w+)","(.)","([^"]*)",(null|"\d+-\d+")((?:,"[^"]*")?)\]'
)


# ---------------------------------------------------------------- kaynak

def sezon_adi(bugun):
    """Temmuz'dan itibaren yeni sezon. 15.10.2026 -> 2026/2027"""
    yil = bugun.year if bugun.month >= 7 else bugun.year - 1
    return f"{yil}/{yil + 1}"


def sayfayi_al(url, deneme=4):
    bekleme = [5, 15, 30, 60]
    son = None
    for i in range(deneme):
        try:
            y = requests.get(url, headers=BASLIKLAR, timeout=45)
            y.raise_for_status()
            return y.text
        except requests.HTTPError as e:
            kod = e.response.status_code if e.response is not None else 0
            son = e
            if kod not in (500, 502, 503, 504):
                raise
        except requests.RequestException as e:
            son = e
        if i < deneme - 1:
            print(f"   (sunucu hatasi, {bekleme[i]} sn sonra tekrar)", flush=True)
            time.sleep(bekleme[i])
    raise son


def kulvar_kodu(baslik, altbaslik):
    for anahtar, kod in KULVARLAR:
        if anahtar.lower() in baslik.lower():
            if kod in ("SAM", "AL", "KON") and ELEME.search(altbaslik or ""):
                return "ELE" if kod == "SAM" else kod
            return kod
    return None


def sezonu_cek(sezon):
    """Sezonun oynanmis maclarini dondurur: {tarih: (kulvar, yer, rakip, skor)}"""
    corba = BeautifulSoup(sayfayi_al(KALIP.format(sezon=sezon)), "html.parser")

    for bag in corba.find_all("a", href=re.compile(r"/Mac/\d+")):
        e = re.search(r"/Mac/(\d+)", bag["href"])
        if e:
            bag.string = f"«M{e.group(1)}:{bag.get_text(strip=True)}»"

    metin = re.sub(r"\s+", " ", corba.get_text(" "))

    isaretler = []
    for anahtar, _ in KULVARLAR:
        for e in re.finditer(re.escape(anahtar), metin):
            isaretler.append((e.start(), anahtar))
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

    bulunan, toplam = {}, 0
    for e in MAC_DESENI.finditer(metin):
        tarih_ham, ev, _mac_id, skor_ham, dep = e.groups()
        kod = kulvar_bul(e.start())
        if kod in (None, "ATLA"):
            continue

        g, a, yil = re.match(r"(\d{1,2})\.(\d{2})\.(\d{4})", tarih_ham).groups()
        tarih = f"{yil}-{a}-{int(g):02d}"

        ev = re.sub(r"\s+", " ", ev).strip(" .,-—–")
        dep = re.sub(r"\s+", " ", dep).strip(" .,-—–")
        if BIZ not in (ev, dep):
            continue
        toplam += 1

        s = re.match(r"(\d+)\s*-\s*(\d+)", skor_ham.strip())
        if not s:
            continue                                  # henuz oynanmamis
        g1, g2 = int(s.group(1)), int(s.group(2))
        bizEv = (ev == BIZ)
        bulunan[tarih] = (kod, "İ" if bizEv else "D",
                          dep if bizEv else ev,
                          f"{g1}-{g2}" if bizEv else f"{g2}-{g1}")
    return bulunan, toplam


# ---------------------------------------------------------------- dosya

def blok_al(icerik):
    e = re.search(r'id:"%s",.*?maclar:\[(.*?)\n    \]' % re.escape(DONEM_ID),
                  icerik, re.S)
    if not e:
        raise SystemExit(f"HATA: '{DONEM_ID}' blogu index.html icinde bulunamadi.")
    return e.group(1)


def satirlari_oku(blok):
    return [m.groups() for m in SATIR_DESENI.finditer(blok)]


def karne(satirlar):
    """Oynanmis maclardan mac sayisi ve puan ortalamasi."""
    g = b = m = 0
    for _t, _k, _y, _r, skor, _l in satirlar:
        if skor == "null":
            continue
        a, y = map(int, skor.strip('"').split("-"))
        if a > y:
            g += 1
        elif a == y:
            b += 1
        else:
            m += 1
    n = g + b + m
    return n, g, b, m, ((g * 3 + b) / n if n else 0.0)


def dogrula(icerik):
    """Yazmadan onceki son kontrol. Sorun varsa gerekce listesi doner."""
    sorun = []

    kotu = re.findall(
        r'\[\s*"\d{4}-\d\d-\d\d"\s*,\s*"[^"]*"\s*,\s*"[^"]*"\s*,\s*"[^"]*"\s*,'
        r'\s*(?!null|")([^,\]]+)', icerik)
    if kotu:
        sorun.append(f"tirnaksiz/gecersiz skor: {kotu[:5]}")

    satirlar = satirlari_oku(blok_al(icerik))
    if not satirlar:
        sorun.append("fb-simdi blogunda hic satir okunamadi")
        return sorun

    tarihler = [t for t, *_ in satirlar]
    if tarihler != sorted(tarihler):
        sorun.append("tarih sirasi bozuk")

    n, g, b, m, ort = karne(satirlar)
    h = re.search(r'\["([^"]+)",\s*"([^"]*)",\s*(\d+),\s*([\d.]+),\s*"suruyor"', icerik)
    if not h:
        sorun.append('HOCALAR icinde "suruyor" satiri bulunamadi')
    else:
        if int(h.group(3)) != n:
            sorun.append(f"HOCALAR mac sayisi {h.group(3)}, fikstur {n}")
        if abs(float(h.group(4)) - round(ort, 2)) > 0.005:
            sorun.append(f"HOCALAR ortalama {h.group(4)}, fikstur {ort:.2f}")
    return sorun


# ---------------------------------------------------------------- ana

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true",
                    help="index.html'e yazmadan neyin degisecegini goster")
    ap.add_argument("--sinama", action="store_true",
                    help="yalnizca kaynaga erisimi sina, dosyaya hic bakma")
    args = ap.parse_args()

    bugun = dt.date.today()

    if args.sinama:
        sezon = sezon_adi(bugun)
        print(f"Kaynak sinamasi: {KALIP.format(sezon=sezon)}")
        bulunan, toplam = sezonu_cek(sezon)
        print(f"   {toplam} mac goruldu, {len(bulunan)} tanesinin skoru var")
        if toplam < EN_AZ_MAC:
            raise SystemExit(
                f"SINAMA KALDI: yalnizca {toplam} mac dondu. Kaynak bu "
                f"sunucudan erisilemiyor ya da sayfa yapisi degismis."
            )
        son = sorted(bulunan)[-5:]
        print("   en son skorlar:")
        for t in son:
            kod, yer, rakip, skor = bulunan[t]
            print(f"      {t}  {kod:4} {yer}  {rakip:22} {skor}")
        print("SINAMA TAMAM — kaynak bu sunucudan okunabiliyor.")
        return
    icerik = io.open(HEDEF, encoding="utf-8").read()
    orijinal = icerik

    satirlar = satirlari_oku(blok_al(icerik))
    if not satirlar:
        raise SystemExit("HATA: fb-simdi blogunda satir okunamadi, desen bozulmus.")

    bekleyen = [
        s for s in satirlar
        if s[4] == "null"
        and dt.date(*map(int, s[0].split("-"))) <= bugun
    ]

    print(f"Guncel donem: {len(satirlar)} satir, "
          f"{sum(1 for s in satirlar if s[4] != 'null')} oynanmis")

    if bekleyen:
        print(f"Skoru bekleyen {len(bekleyen)} mac:")
        for t, k, y, r, _s, _l in bekleyen:
            print(f"   {t}  {k:4} {y}  {r}")
    else:
        print("Skoru bekleyen mac yok.")

    # Bekleyen olmasa da kaynagi okuyoruz: fiksturde hic olmayan bir mac
    # (kupa kurasi, eklenen hazirlik maci) ancak boyle farkedilir.
    # Gunde bir sayfa, kaynaga yuk degil.
    sezon = sezon_adi(bugun)
    print(f"\nKaynak taraniyor: {sezon}")
    bulunan, toplam = sezonu_cek(sezon)
    print(f"   {toplam} mac goruldu, {len(bulunan)} tanesinin skoru var")

    if toplam < EN_AZ_MAC:
        raise SystemExit(
            f"HATA: kaynaktan yalnizca {toplam} mac dondu, en az {EN_AZ_MAC} "
            f"bekleniyordu. Sayfa yapisi degismis olabilir. "
            f"index.html'e dokunulmadi."
        )

    # Skorlari yaz
    yazilan, eksik = [], []
    for t, k, y, r, _s, link in bekleyen:
        if t not in bulunan:
            eksik.append((t, r))
            continue
        kod, yer, rakip_kaynak, skor = bulunan[t]
        eski = f'["{t}","{k}","{y}","{r}",null{link}]'
        yeni = f'["{t}","{k}","{y}","{r}","{skor}"{link}]'
        if eski not in icerik:
            raise SystemExit(f"HATA: {t} satiri yerinde bulunamadi, yazilmadi.")
        icerik = icerik.replace(eski, yeni, 1)
        not_ = ""
        if kod != k:
            not_ += f"  [kulvar farki: kaynak {kod}]"
        if yer != y:
            not_ += f"  [saha farki: kaynak {yer}]"
        yazilan.append((t, r, skor, not_))

    if eksik:
        print("\nKaynakta skoru henuz olmayanlar (sonraki calismada tekrar denenir):")
        for t, r in eksik:
            print(f"   {t}  {r}")

    # Kaynakta oynanmis ama fikstürümüzde hic bulunmayan maclar: kupa kurasi
    # cekilmis ya da hazirlik maci eklenmis olabilir. Elle bakilmasi gerekir.
    bizdeki = {s[0] for s in satirlar}
    yeni = {t: v for t, v in bulunan.items() if t not in bizdeki}
    if yeni:
        print("\nUYARI: kaynakta oynanmis ama fiksturde olmayan mac var.")
        print("Bunlar kendiliginden eklenmez, index.html'e elle girilmeli:")
        for t in sorted(yeni):
            kod, yer, rakip, skor = yeni[t]
            print(f'   ["{t}","{kod}","{yer}","{rakip}","{skor}"]')
        try:
            io.open(ISARET_DOSYASI, "w", encoding="utf-8").write(
                "\n".join(f'["{t}","{yeni[t][0]}","{yeni[t][1]}",'
                          f'"{yeni[t][2]}","{yeni[t][3]}"]'
                          for t in sorted(yeni)) + "\n")
        except Exception:
            pass

    if not yazilan:
        print("\nYazilacak yeni skor yok. Dosyaya dokunulmadi.")
        return

    print("\nYazilan skorlar:")
    for t, r, skor, not_ in yazilan:
        print(f"   {t}  {r:22} {skor}{not_}")

    # Karneyi yeniden hesapla
    satirlar = satirlari_oku(blok_al(icerik))
    n, g, b, m, ort = karne(satirlar)
    h = re.search(r'(\["([^"]+)",\s*"([^"]*)",\s*)(\d+)(,\s*)([\d.]+)(,\s*"suruyor")',
                  icerik)
    if not h:
        raise SystemExit('HATA: HOCALAR icinde "suruyor" satiri bulunamadi.')
    icerik = icerik[:h.start()] + \
        f"{h.group(1)}{n}{h.group(5)}{ort:.2f}{h.group(7)}" + icerik[h.end():]
    print(f"\nKarne: {n} mac  {g}G {b}B {m}M  ort {ort:.2f}  ({h.group(2)})")

    # Son guncelleme tarihi
    icerik = re.sub(
        r'const SON_GUNCELLEME = "[^"]*";',
        f'const SON_GUNCELLEME = "{bugun.day} {AYLAR[bugun.month-1]} {bugun.year}";',
        icerik)

    sorun = dogrula(icerik)
    if sorun:
        print("\nDOGRULAMA KALDI — dosyaya yazilmadi:")
        for s in sorun:
            print("   -", s)
        raise SystemExit(1)
    print("Dogrulama tamam.")

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
