# --- ADIM 1: Gerekli Kütüphaneler ---
print("Kütüphaneler kontrol ediliyor...")
!pip install xarray netCDF4 cartopy matplotlib numpy
print("Hazır.")

import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import os
import warnings
from datetime import datetime, timedelta, time
import numpy as np

# --- 2. GLOBAL AYARLAR ---

KAYIT_KLASORU = '.'

# ZAMAN ADIMLARI (Analiz, Yarın, Ertesi Gün)
TAHMIN_ADIMLARI = {
    0: "000h",
    4: "024h",
    8: "048h"
}

# BÖLGELER VE KOORDİNATLAR
DOMAINS = {
    "GFS":      [-20, 60, 25, 65],   # Avrupa Geneli
    "Domain1":  [25, 45, 34, 43],    # Türkiye
    "Domain2":  [26, 32, 39, 42.5]   # Marmara
}

warnings.filterwarnings('ignore')

# --- 3. HARİTA ÇİZDİRME MOTORU ---

def harita_cizdir(
    data_array_doldurma, model_basligi, parametre_adi_baslik,
    tahmin_zamani_str, tahmin_saati_h_str, kaydedilecek_dosya_adi,
    renk_cubugu_etiketi, renk_skalasi, renk_seviyeleri,
    harita_sinirlari, 
    data_array_cizgiler=None, cizgi_seviyeleri=None,
    cizgi_renkleri='black', cizgi_etiketleri_goster=False
    ):
    try:
        print(f"---> {kaydedilecek_dosya_adi}")
        fig = plt.figure(figsize=(12, 10))
        ax = plt.axes(projection=ccrs.Mercator())
        
        # Domain sınırlarını ayarla
        ax.set_extent(harita_sinirlari, crs=ccrs.PlateCarree())

        # 1. Dolgu (extend='both' taşan değerleri de boyar)
        kontur_dolgu = data_array_doldurma.plot.contourf(
            ax=ax, transform=ccrs.PlateCarree(), levels=renk_seviyeleri,
            cmap=renk_skalasi, add_colorbar=False, extend='both'
        )
        cbar = plt.colorbar(kontur_dolgu, ax=ax, orientation='vertical', pad=0.02, shrink=0.8)
        cbar.set_label(renk_cubugu_etiketi)

        # 2. Çizgi (Opsiyonel)
        if data_array_cizgiler is not None:
            kontur_cizgi = data_array_cizgiler.plot.contour(
                ax=ax, transform=ccrs.PlateCarree(), levels=cizgi_seviyeleri,
                colors=cizgi_renkleri, linewidths=0.8
            )
            if cizgi_etiketleri_goster:
                ax.clabel(kontur_cizgi, inline=True, fontsize=8, fmt='%i')

        # Harita Süslemeleri
        ax.add_feature(cfeature.COASTLINE)
        ax.add_feature(cfeature.BORDERS, linestyle=':')
        ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)

        plt.title(f"{model_basligi}\n{parametre_adi_baslik} ({tahmin_saati_h_str})", fontsize=12)

        tam_kayit_yolu = os.path.join(KAYIT_KLASORU, kaydedilecek_dosya_adi)
        plt.savefig(tam_kayit_yolu, dpi=100, bbox_inches='tight')
        plt.close(fig)
        
    except Exception as e:
        print(f"     HATA ({kaydedilecek_dosya_adi}): {e}")

# --- 4. ANA PROGRAM ---

def main():
    print("======================================================")
    print(f"NOAA AI Harita Betiği (Final Düzeltilmiş) - {datetime.now()}")
    print("======================================================")

    # --- ADIM A: TARİH HESAPLAMA ---
    utc_simdi = datetime.utcnow()
    if utc_simdi.time() < time(6, 0): 
        model_tarihi = utc_simdi.date() - timedelta(days=1)
    else:
        model_tarihi = utc_simdi.date()

    yil_str = model_tarihi.strftime('%Y')
    ay_gun_str = model_tarihi.strftime('%m%d')
    tam_tarih_str = model_tarihi.strftime('%Y%m%d')

    dosya_adi = f"FOUR_v200_GFS_{tam_tarih_str}00_f000_f240_06.nc"
    dosya_linki = f"https://noaa-oar-mlwp-data.s3.amazonaws.com/FOUR_v200_GFS/{yil_str}/{ay_gun_str}/{dosya_adi}"
    indirilen_dosya_yolu = os.path.join(KAYIT_KLASORU, dosya_adi)

    # --- ADIM B: İNDİRME ---
    if not os.path.exists(indirilen_dosya_yolu):
        print(f"İndiriliyor (4.3GB): {dosya_linki}")
        os.system(f"wget -O {indirilen_dosya_yolu} {dosya_linki}")
    else:
        print("Dosya zaten mevcut, indirme atlanıyor.")

    print("\nVeri işleniyor...")
    try:
        ds = xr.open_dataset(indirilen_dosya_yolu)
        baslik = f"AI Model (FOUR_v200_GFS) - {tam_tarih_str} 00Z"

        # =====================================================================
        # GÖREVLER
        # =====================================================================

        # --- GÖREV 1: 2m SICAKLIK (DİNAMİK SKALA) ---
        print("\n>>> Görev 1: 2m Sıcaklık (Dinamik Skala)")
        t2_c = ds['t2'] - 273.15
        for idx, saat in TAHMIN_ADIMLARI.items():
            d = t2_c.isel(time=idx)
            t_str = d.time.dt.strftime('%d-%H:00').item()
            
            for dom, box in DOMAINS.items():
                if dom == "Domain2": # MARMARA (Hassas)
                    skala = np.arange(-5, 35.5, 0.5)
                elif dom == "Domain1": # TÜRKİYE
                    skala = np.arange(-15, 41, 1)
                else: # AVRUPA (GFS)
                    skala = np.arange(-30, 46, 2)

                harita_cizdir(d, baslik, f"2m Sıcaklık ({dom})", t_str, f"+{idx*6}h",
                              f"temp2m_{saat}_{dom}.png", "°C", 'jet', skala, box)

        # --- GÖREV 2: SU BUHARI (TCWV) ---
        print("\n>>> Görev 2: Precipitable Water")
        tcwv = ds['tcwv']
        for idx, saat in TAHMIN_ADIMLARI.items():
            d = tcwv.isel(time=idx)
            t_str = d.time.dt.strftime('%d-%H:00').item()
            for dom, box in DOMAINS.items():
                harita_cizdir(d, baslik, f"Precipitable Water ({dom})", t_str, f"+{idx*6}h",
                              f"pwat_{saat}_{dom}.png", "mm", 'nipy_spectral_r', np.arange(0, 70, 2), box)

        # --- GÖREV 3: 700 hPa NEM ---
        print("\n>>> Görev 3: 700 hPa Nem")
        try:
            var = ds['r'].sel(level=700)
            for idx, saat in TAHMIN_ADIMLARI.items():
                d = var.isel(time=idx)
                t_str = d.time.dt.strftime('%d-%H:00').item()
                for dom, box in DOMAINS.items():
                    harita_cizdir(d, baslik, f"700 hPa Nem ({dom})", t_str, f"+{idx*6}h",
                                  f"rh700_{saat}_{dom}.png", "%", 'Blues', np.arange(0, 101, 5), box)
        except: pass

        # --- GÖREV 4: 850 hPa SICAKLIK ---
        print("\n>>> Görev 4: 850 hPa Sıcaklık")
        try:
            var = ds['t'].sel(level=850) - 273.15
            for idx, saat in TAHMIN_ADIMLARI.items():
                d = var.isel(time=idx)
                t_str = d.time.dt.strftime('%d-%H:00').item()
                for dom, box in DOMAINS.items():
                    harita_cizdir(d, baslik, f"850 hPa Sıcaklık ({dom})", t_str, f"+{idx*6}h",
                                  f"temp850_{saat}_{dom}.png", "°C", 'coolwarm', np.arange(-25, 26, 2), box)
        except: pass

        # --- GÖREV 5: BASINÇ (MSL) ---
        print("\n>>> Görev 5: Basınç")
        msl_hpa = ds['msl'] / 100.0
        for idx, saat in TAHMIN_ADIMLARI.items():
            d = msl_hpa.isel(time=idx)
            t_str = d.time.dt.strftime('%d-%H:00').item()
            for dom, box in DOMAINS.items():
                harita_cizdir(d, baslik, f"Basınç ({dom})", t_str, f"+{idx*6}h",
                              f"basinc_{saat}_{dom}.png", "hPa", 'coolwarm_r', np.arange(980, 1045, 4), box)

        # --- GÖREV 6: YER SICAKLIĞI (SKIN TEMP) ---
        print("\n>>> Görev 6: Skin Temp")
        try:
            if 'skt' in ds:
                var = ds['skt'] - 273.15
                for idx, saat in TAHMIN_ADIMLARI.items():
                    d = var.isel(time=idx)
                    t_str = d.time.dt.strftime('%d-%H:00').item()
                    for dom, box in DOMAINS.items():
                        harita_cizdir(d, baslik, f"Yer Sıcaklığı ({dom})", t_str, f"+{idx*6}h",
                                      f"skt_{saat}_{dom}.png", "°C", 'inferno', np.arange(-20, 45, 2), box)
        except: pass

        # --- GÖREV 7: DÜŞEY HIZ (500hPa) ---
        print("\n>>> Görev 7: Düşey Hız")
        try:
            if 'w' in ds:
                var = ds['w'].sel(level=500)
                for idx, saat in TAHMIN_ADIMLARI.items():
                    d = var.isel(time=idx)
                    t_str = d.time.dt.strftime('%d-%H:00').item()
                    for dom, box in DOMAINS.items():
                        harita_cizdir(d, baslik, f"500 hPa Düşey Hız ({dom})", t_str, f"+{idx*6}h",
                                      f"vertvel500_{saat}_{dom}.png", "Pa/s", 'RdBu_r', np.arange(-2, 2.1, 0.2), box)
        except: pass

        # --- GÖREV 8: RÜZGAR (10m) ---
        print("\n>>> Görev 8: Rüzgar Hızı")
        ws = np.sqrt(ds['u10']*2 + ds['v10']*2)
        for idx, saat in TAHMIN_ADIMLARI.items():
            d = ws.isel(time=idx)
            t_str = d.time.dt.strftime('%d-%H:00').item()
            for dom, box in DOMAINS.items():
                harita_cizdir(d, baslik, f"10m Rüzgar ({dom})", t_str, f"+{idx*6}h",
                              f"wind10_{saat}_{dom}.png", "m/s", 'viridis', np.arange(0, 31, 2), box)

        # --- GÖREV 9: 500 hPa Z & T ---
        print("\n>>> Görev 9: 500 hPa Analizi")
        z500 = ds['z'].sel(level=500) / 9.80665
        t500 = ds['t'].sel(level=500) - 273.15
        for idx, saat in TAHMIN_ADIMLARI.items():
            dt = t500.isel(time=idx)
            dz = z500.isel(time=idx)
            t_str = dt.time.dt.strftime('%d-%H:00').item()
            for dom, box in DOMAINS.items():
                harita_cizdir(dt, baslik, f"500 hPa Z & T ({dom})", t_str, f"+{idx*6}h",
                              f"z500_{saat}_{dom}.png", "°C", 'coolwarm', np.arange(-40, 0, 2), box,
                              dz, np.arange(4800, 6000, 60), 'black', True)

    except Exception as e:
        print(f"GENEL HATA: {e}")

    finally:
        # --- TEMİZLİK ---
        if 'ds' in locals() and ds: ds.close()
        if os.path.exists(indirilen_dosya_yolu):
            os.remove(indirilen_dosya_yolu)
            print("\nTemizlik yapıldı: İndirilen dosya silindi.")

    print("======================================================")
    print("Betik Tamamlandı.")

# Ana fonksiyonu direkt çağırıyoruz (Colab için en kolayı)
main()     bunu nasıl eklicez oraya bunu collab ortamında yaptık dosya olarak nasıl indiricez
