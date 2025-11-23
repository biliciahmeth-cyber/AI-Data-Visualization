#!/usr/bin/env python3
# -- coding: utf-8 --

"""
NOAA AI Model - TURBO EDITION (Multiprocessing)
Bu versiyon, haritaları paralel (aynı anda) çizerek işlem süresini kısaltır.
Yerel bilgisayar ve Sunucu uyumludur.
"""

# --- Gerekli Kütüphaneler ---
# Kurulum: pip install xarray netCDF4 cartopy matplotlib numpy requests pandas

import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import os
import warnings
from datetime import datetime, timedelta, time
import numpy as np
import requests
import shutil
import pandas as pd
from multiprocessing import Pool, cpu_count # <-- Hızın sırrı burada

# --- 1. GLOBAL AYARLAR ---

# Çıktıların kaydedileceği yer.
KAYIT_KLASORU = '.' 

# AYNI ANDA KAÇ HARİTA ÇİZİLSİN?
# Bilgisayarın iyiyse (8+ çekirdek) burayı 6-8 yapabilirsin.
# Sunucu veya orta halli laptop için 4 idealdir.
ISCI_SAYISI = 4

# ZAMAN ADIMLARI
# 0=Analiz, 4=+24h, 8=+48h
TAHMIN_ADIMLARI = {
    0: "f000",
    4: "f024",
    8: "f048"
}

# BÖLGELER
DOMAINS = {
    "europe":   [-20, 60, 25, 65],
    "turkey":   [25, 45, 34, 43],
    "marmara":  [26, 32, 39, 42.5]
}

# MODELLER
MODELLER = [
    "FOUR_v200_GFS",  # Nvidia
    "GRAP_v100_GFS",  # Google
    "PANG_v100_GFS",  # Huawei
    "AURO_v100_GFS"   # Microsoft
]

warnings.filterwarnings('ignore')

# --- 2. YARDIMCI FONKSİYONLAR ---

def python_ile_indir(url, hedef_yol):
    """Dosyayı indirir."""
    print(f"   >> İndiriliyor: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        with requests.get(url, stream=True, headers=headers, timeout=120) as r:
            r.raise_for_status()
            with open(hedef_yol, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
        print("   >> İndirme Tamamlandı.")
        return True
    except Exception as e:
        print(f"   >> İndirme HATASI: {e}")
        return False

# --- PARALEL ÇALIŞACAK FONKSİYON (İŞÇİ) ---
# Bu fonksiyon ana programdan bağımsız çalışır.
def plot_wrapper(args):
    """
    Tek bir haritayı çizen fonksiyon.
    Multiprocessing havuzuna bu fonksiyon gönderilir.
    """
    # Argüman paketini aç
    (data_slice, title_main, title_sub, time_str, fcst_h, filename, label, cmap, levels, extent, c_data_slice, c_levels) = args
    
    try:
        # Matplotlib backend ayarı (Hata almamak için)
        plt.switch_backend('Agg') 
        
        fig = plt.figure(figsize=(12, 10))
        ax = plt.axes(projection=ccrs.Mercator())
        ax.set_extent(extent, crs=ccrs.PlateCarree())

        # 1. Dolgu
        fill = data_slice.plot.contourf(
            ax=ax, transform=ccrs.PlateCarree(), levels=levels, cmap=cmap, add_colorbar=False, extend='both'
        )
        cbar = plt.colorbar(fill, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
        cbar.set_label(label)

        # 2. Çizgi (Varsa)
        if c_data_slice is not None:
            lines = c_data_slice.plot.contour(
                ax=ax, transform=ccrs.PlateCarree(), levels=c_levels, colors='black', linewidths=0.8
            )
            ax.clabel(lines, inline=True, fontsize=8, fmt='%i')

        # Süslemeler
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linestyle=':', linewidth=0.6)

        plt.title(f"{title_main}\n{title_sub} ({fcst_h}) - Geçerlilik: {time_str} (Yerel)", fontsize=10)

        save_path = os.path.join(KAYIT_KLASORU, filename)
        plt.savefig(save_path, dpi=90, bbox_inches='tight')
        plt.close(fig) # Hafızayı temizle
        
        # Başarılı olursa dosya adını dön (Log için)
        return f"OK: {filename}"
        
    except Exception as e:
        return f"HATA: {filename} - {e}"

# --- 3. ANA PROGRAM ---

def main():
    baslangic_zamani = datetime.now()
    print(f"\n=== AI WEATHER PIPELINE (TURBO MOD) BAŞLATILDI: {baslangic_zamani} ===\n")
    print(f"   >> Paralel İşlemci Sayısı: {ISCI_SAYISI}")

    # Tarih Hesapla
    utc_now = datetime.utcnow()
    model_date = utc_now.date() - timedelta(days=1) if utc_now.time() < time(6, 0) else utc_now.date()
    
    yyyy = model_date.strftime('%Y')
    mmdd = model_date.strftime('%m%d')
    full_date = model_date.strftime('%Y%m%d')
    
    print(f"Hedef Tarih (00Z): {full_date}")

    # --- MODEL DÖNGÜSÜ ---
    for model_name in MODELLER:
        print(f"\n--------------------------------------------------")
        print(f"İŞLENEN MODEL: {model_name}")
        print(f"--------------------------------------------------")

        nc_filename = f"{model_name}_{full_date}00_f000_f240_06.nc"
        url = f"https://noaa-oar-mlwp-data.s3.amazonaws.com/{model_name}/{yyyy}/{mmdd}/{nc_filename}"
        local_path = os.path.join(KAYIT_KLASORU, nc_filename)

        # 1. İNDİR
        if not os.path.exists(local_path):
            if not python_ile_indir(url, local_path):
                print(f"!!! {model_name} İNDİRİLEMEDİ, ATLANİYOR !!!")
                continue
        else:
            print("   >> Dosya zaten var.")

        # 2. GÖREVLERİ HAZIRLA (Çizmeden önce listeye atıyoruz)
        gorev_listesi = [] # Yapılacak işler paketi
        
        try:
            # Dosyayı aç (chunks={} ile RAM'i patlatmadan açar)
            ds = xr.open_dataset(local_path, chunks={})
            short_name = model_name.split('_')[0] 
            main_title = f"{short_name} AI Model - {full_date} 00Z"

            # Parametre Tanımları (Adı, Başlığı, DosyaEki, Birimi, Renk, İşlem, ÖzelDurum)
            tasks_config = [
                ('t2', '2m Temperature', 'temp_2m', '°C', 'Spectral_r', lambda x: x-273.15, None),
                ('u10', '10m Wind Speed', 'wind_10m', 'm/s', 'YlOrRd', None, 'calc_wind'),
                ('msl', 'MSLP', 'mslp', 'hPa', 'RdBu_r', lambda x: x/100.0, None),
                ('tcwv', 'Precipitable Water', 'pr_wtr', 'mm', 'YlGnBu', None, None),
                ('r', '700 hPa Humidity', 'rh_700', '%', 'Blues', None, 'sel_700'),
                ('t', '850 hPa Temp', 'temp_850', '°C', 'coolwarm', lambda x: x-273.15, 'sel_850'),
                ('skt', 'Skin Temperature', 'skt', '°C', 'inferno', lambda x: x-273.15, None),
                ('w', '500 hPa Vert. Vel.', 'w_500', 'Pa/s', 'RdBu_r', None, 'sel_500'),
                ('z', '500 hPa Geopotential', 'hgt_500', 'gpm', 'RdBu_r', None, 'sel_500_combo')
            ]

            print("   >> Veriler hazırlanıyor ve belleğe alınıyor...")

            for var_name, title, file_prefix, unit, cmap_def, func, special in tasks_config:
                
                # Veri var mı kontrolü
                if var_name not in ds and special != 'calc_wind': continue

                # --- VERİYİ BELLEĞE ÇEK (.load()) ---
                # Multiprocessing için verinin diske bağlı kalmaması, RAM'de olması lazım.
                if special == 'calc_wind':
                    data = np.sqrt(ds['u10']*2 + ds['v10']*2).load()
                elif special == 'sel_700': data = ds[var_name].sel(level=700).load()
                elif special == 'sel_850': data = ds[var_name].sel(level=850).load()
                elif special == 'sel_500': data = ds[var_name].sel(level=500).load()
                elif special == 'sel_500_combo':
                    data = ds['t'].sel(level=500).load()
                    c_data = ds['z'].sel(level=500).load()
                else:
                    data = ds[var_name].load()

                # Birim Dönüşümü
                if func and special != 'sel_500_combo': data = func(data)
                if special == 'sel_500_combo':
                    data = data - 273.15
                    c_data = c_data / 9.80665

                # Kombinasyonları Listele
                for idx, step in TAHMIN_ADIMLARI.items():
                    # Zamanı kes
                    d_slice = data.isel(time=idx)
                    # Türkiye Saati Ayarı
                    zaman_tr = d_slice.time.values + np.timedelta64(3, 'h')
                    valid_time = pd.to_datetime(zaman_tr).strftime('%d %b %H:00')

                    c_d_slice = None
                    c_levels = None
                    if special == 'sel_500_combo':
                        c_d_slice = c_data.isel(time=idx)
                        c_levels = np.arange(4800, 6000, 60)

                    for dom, extent in DOMAINS.items():
                        # Skala Ayarları
                        levels = None
                        if file_prefix in ['temp_2m', 'skt']:
                            if dom == "marmara": levels = np.arange(-5, 35.5, 0.5)
                            elif dom == "turkey": levels = np.arange(-15, 41, 1)
                            else: levels = np.arange(-30, 46, 2)
                        elif file_prefix == 'wind_10m': levels = np.arange(0, 31, 2)
                        elif file_prefix == 'mslp': levels = np.arange(980, 1045, 4)
                        elif file_prefix == 'pr_wtr': levels = np.arange(0, 70, 2)
                        elif file_prefix == 'rh_700': levels = np.arange(0, 101, 5)
                        elif file_prefix == 'temp_850': levels = np.arange(-25, 26, 2)
                        elif file_prefix == 'w_500': levels = np.arange(-2, 2.1, 0.2)
                        elif file_prefix == 'hgt_500': levels = np.arange(-40, 0, 2)

                        fname = f"{file_prefix}{step}{dom}_{short_name}.png"
                        
                        # Bu paketi işçiye vereceğiz
                        gorev_paketi = (
                            d_slice, main_title, title, valid_time, step, fname, unit, cmap_def, levels, extent, c_d_slice, c_levels
                        )
                        gorev_listesi.append(gorev_paketi)

            print(f"   >> Toplam {len(gorev_listesi)} harita için paralel çizim başlıyor...")
            
            # 3. PARALEL ÇİZİMİ BAŞLAT (Havuz Sistemi)
            # Bu kısım bilgisayarın çekirdeklerini devreye sokar
            with Pool(processes=ISCI_SAYISI) as pool:
                # İşleri dağıt ve sonuçları bekle
                for sonuc in pool.imap_unordered(plot_wrapper, gorev_listesi):
                    # Çıktıyı çok kirletmemek için sadece hataları basabiliriz
                    if "HATA" in sonuc:
                        print(f"      !!! {sonuc}")
            
            print("   >> Çizimler tamamlandı.")

        except Exception as e:
            print(f"   !!! İŞLEME HATASI ({model_name}): {e}")

        finally:
            # 4. TEMİZLİK
            if 'ds' in locals() and ds: ds.close()
            if os.path.exists(local_path):
                os.remove(local_path)
                print(f"   >> Temizlik: {nc_filename} silindi.")

    print("\n=== TÜM MODELLER BİTTİ ===")
    print(f"Toplam Süre: {datetime.now() - baslangic_zamani}")

if _name_ == "_main_":
    main()
