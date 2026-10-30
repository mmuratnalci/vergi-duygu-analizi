"""Türkçe yorumlar için kural tabanlı duygu analizi (Streamlit)."""

import io
import re
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Duygu Analizi", page_icon="💬", layout="wide")

RENKLER = {"Olumlu": "#2e9e6b", "Olumsuz": "#d64545", "Nötr": "#8a94a6"}
SIRA = ["Olumlu", "Olumsuz", "Nötr"]
KODLAMALAR = ["utf-8-sig", "utf-8", "cp1254", "iso-8859-9", "utf-16", "cp1252"]

# Sözcük kökleri; sözcük bu köklerden biriyle başlıyorsa eşleşir.
OLUMLU_KOKLER = [
    "güzel", "iyi", "harika", "mükemmel", "muhteşem", "süper", "başarılı", "memnun",
    "teşekkür", "sağol", "tavsiye", "öneri", "hızlı", "kaliteli", "kusursuz", "rahat",
    "faydalı", "yararlı", "pratik", "kolay", "temiz", "şahane", "bayıl", "sevdi",
    "seviyor", "sevi", "beğen", "mutlu", "keyif", "memnuniyet", "olumlu", "doğru",
    "ilgili", "samimi", "güler yüz", "uygun", "ucuz", "değer", "tatmin", "çözüm",
    "çözüldü", "sorunsuz", "profesyonel", "açık", "anlaşılır", "yardımcı", "yardım",
    "destek", "başarı", "efsane", "bayıldı", "eksiksiz", "kibar", "nazik", "güvenilir",
    "güven", "stabil", "akıcı", "özenli", "ideal", "tam puan", "fevkalade", "olağanüstü",
]
OLUMSUZ_KOKLER = [
    "kötü", "berbat", "rezalet", "felaket", "yavaş", "pahalı", "sorun", "problem",
    "şikayet", "şikâyet", "memnun değil", "hayal kırıklığı", "yetersiz", "başarısız",
    "kırık", "bozuk", "arıza", "hata", "geç", "gecik", "mağdur", "mağduriyet",
    "karmaşık", "zor", "saçma", "kaba", "ilgisiz", "pişman", "rezil", "çöp",
    "iğrenç", "yanlış", "eksik", "çalışmıyor", "çalışmadı", "donuyor", "kasıyor",
    "çöktü", "çöküyor", "sinir", "bıktı", "bık", "dolandır", "aldat", "sahte",
    "haksız", "adaletsiz", "adalet", "yüksek", "kesinlikle önermem", "önermiyorum",
    "bekledik", "bekletil", "cevap vermiyor", "ulaşılamıyor", "ulaşamadım", "açılmıyor",
    "kızgın", "kızdı", "üzücü", "üzgün", "stres", "zorlu", "yük", "ağır", "can sıkıcı",
    "vasat", "kalitesiz", "özensiz", "güvensiz", "tehlikeli", "kayıp", "israf",
]
# Olumsuzlama eki alabilen fiil kökleri (beğenmedim, sevmedim, memnun kalmadım ...).
FIIL_KOKLER = ["beğen", "sev", "tavsiye et", "öner", "tatmin ol", "yardım", "çöz", "güven"]
OLUMSUZLAYICILAR = {"değil", "değildi", "degil", "yok", "hiç", "asla", "katiyen", "ne yazık ki"}
OLUMSUZLAMA_SONEKLERI = (
    "madı", "medi", "madım", "medim", "madık", "medik", "mıyor", "miyor", "muyor", "müyor",
    "maz", "mez", "mamış", "memiş", "mıyoruz", "miyoruz", "mıyorum", "miyorum",
    "madan", "meden", "mayacak", "meyecek",
)
BASLANGIC_OLUMSUZ = {"hiç", "asla", "katiyen"}

DURAK_SOZCUKLER = set(
    """acaba ama ancak artık aslında az bana bazen bazı belki ben beni benim beri bile bir birçok biri birkaç
    biz bizi bizim bu buna bunda bundan bunlar bunu bunun burada çok çünkü da daha de defa değil diye
    dolayı en fakat gibi hem hep hepsi her herhangi hiç için ile ise işte kadar kendi kendine ki kim kimse
    mi mı mu mü nasıl ne neden nerede nereye niçin niye o olarak olan olduğu olmak olsa oldu olur olarak
    onlar onu onun öyle pek ise sadece sanki şey şu şöyle şunu tabii tüm ve veya ya yani yine zaten
    var ben sen siz size sizin ona bunu şunlar biraz bütün diğer sonra önce göre kez ayrıca üzere
    olması olmasi oldukça edilen edildi etti ettim eden etmek yap yaptı yaptım yapıyor yapılan
    gün gibi bence bende senin onlarla bir iki üç mü mi bu şu""".split()
)


def kucult(metin: str) -> str:
    """Türkçe harf kurallarına uygun küçük harfe çevirir."""
    return metin.replace("İ", "i").replace("I", "ı").lower()


def sozcukle(metin: str) -> list[str]:
    return re.findall(r"[a-zçğıöşüâîû]+", kucult(metin))


def olumsuzlama_mi(sozcuk: str) -> bool:
    return sozcuk in OLUMSUZLAYICILAR or sozcuk.endswith(OLUMSUZLAMA_SONEKLERI)


def skorla(metin) -> float:
    """Olumlu +1, olumsuz -1 puan verir; yakındaki olumsuzlama işareti puanı tersine çevirir."""
    if not isinstance(metin, str) or not metin.strip():
        return 0.0
    kelimeler = sozcukle(metin)
    toplam = 0.0
    for i, k in enumerate(kelimeler):
        puan = 0.0
        fiil_olumsuz = False
        for kok in FIIL_KOKLER:
            if k.startswith(kok) and re.match(r"^(m[ae]|m[ıiuü]yor)", k[len(kok):]):
                fiil_olumsuz = True
                break
        if fiil_olumsuz:
            puan = -1.0
        elif any(k.startswith(kok) for kok in OLUMLU_KOKLER if " " not in kok):
            puan = 1.0
        elif any(k.startswith(kok) for kok in OLUMSUZ_KOKLER if " " not in kok):
            puan = -1.0
        if puan == 0.0:
            continue
        if not fiil_olumsuz:
            sonraki = kelimeler[i + 1 : i + 3]
            onceki = kelimeler[max(0, i - 1) : i]
            if any(olumsuzlama_mi(s) for s in sonraki) or any(o in BASLANGIC_OLUMSUZ for o in onceki):
                puan = -puan
        toplam += puan
    # Çok sözcüklü ifadeler
    kucuk = kucult(metin)
    for ifade in (k for k in OLUMLU_KOKLER if " " in k):
        if ifade in kucuk:
            toplam += 1
    for ifade in (k for k in OLUMSUZ_KOKLER if " " in k):
        if ifade in kucuk:
            toplam -= 1
    return toplam


def sinifla(puan: float) -> str:
    if puan > 0:
        return "Olumlu"
    if puan < 0:
        return "Olumsuz"
    return "Nötr"


@st.cache_data(show_spinner=False)
def dosya_oku(veri: bytes, ad: str) -> pd.DataFrame:
    if ad.lower().endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(veri), engine="openpyxl")
    son_hata = None
    for kodlama in KODLAMALAR:
        try:
            metin = veri.decode(kodlama)
        except (UnicodeDecodeError, UnicodeError) as e:
            son_hata = e
            continue
        try:
            return pd.read_csv(io.StringIO(metin), sep=None, engine="python")
        except Exception as e:  # ayraç algılanamazsa virgül dene
            son_hata = e
            try:
                return pd.read_csv(io.StringIO(metin))
            except Exception as e2:
                son_hata = e2
    raise ValueError(f"Dosya okunamadı: {son_hata}")


def analiz_et(seri: pd.Series) -> pd.DataFrame:
    metinler = seri.fillna("").astype(str).str.strip()
    sonuc = pd.DataFrame({"Yorum": metinler})
    sonuc = sonuc[sonuc["Yorum"].ne("") & sonuc["Yorum"].str.lower().ne("nan")].copy()
    sonuc["Puan"] = sonuc["Yorum"].map(skorla)
    sonuc["Duygu"] = sonuc["Puan"].map(sinifla)
    return sonuc


def sik_kelimeler(metinler: pd.Series, adet: int = 15) -> pd.DataFrame:
    sayac = Counter()
    for m in metinler:
        for k in sozcukle(m):
            if len(k) > 2 and k not in DURAK_SOZCUKLER:
                sayac[k] += 1
    return pd.DataFrame(sayac.most_common(adet), columns=["Kelime", "Adet"])


st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 1100px;}
    h1 {font-weight: 700; letter-spacing: -0.5px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("💬 Yorum Duygu Analizi")
st.caption("Türkçe yorumlarınızı yükleyin; olumlu, olumsuz ve nötr olarak otomatik sınıflandırılsın.")
st.info(
    "Bu analiz **kural tabanlı** çalışır: Türkçe olumlu/olumsuz sözcük listeleri ve olumsuzlama "
    "ifadelerine dayanır. Yapay zekâ modeli kullanmaz; ironi, deyim ve bağlama dayalı anlamları "
    "kaçırabilir ve **hata yapabilir**. Sonuçları kontrol ederek kullanın.",
    icon="ℹ️",
)

yuklenen = st.file_uploader("CSV veya Excel (.xlsx) dosyası yükleyin", type=["csv", "xlsx"])

if yuklenen is None:
    st.write("Başlamak için bir dosya yükleyin.")
    st.stop()

try:
    df = dosya_oku(yuklenen.getvalue(), yuklenen.name)
except Exception as hata:
    st.error(f"Dosya okunamadı. Lütfen geçerli bir CSV veya Excel dosyası yükleyin. ({hata})")
    st.stop()

if df.empty or len(df.columns) == 0:
    st.warning("Dosya boş görünüyor.")
    st.stop()

df.columns = [str(c) for c in df.columns]

st.subheader("Veri Önizleme")
st.caption(f"Toplam {len(df)} satır, {len(df.columns)} sütun. İlk 10 satır:")
st.dataframe(df.head(10), use_container_width=True)

metin_sutunlari = [c for c in df.columns if df[c].dtype == object]
secenekler = metin_sutunlari or list(df.columns)
sutun = st.selectbox("Analiz edilecek yorum sütununu seçin", secenekler)

if not st.button("Analiz Et", type="primary"):
    st.stop()

sonuc = analiz_et(df[sutun])
bos_sayisi = len(df) - len(sonuc)
if bos_sayisi:
    st.warning(f"{bos_sayisi} boş veya eksik yorum analiz dışı bırakıldı.")
if sonuc.empty:
    st.error("Seçilen sütunda analiz edilecek yorum bulunamadı.")
    st.stop()

dagilim = sonuc["Duygu"].value_counts().reindex(SIRA, fill_value=0).reset_index()
dagilim.columns = ["Duygu", "Adet"]

st.subheader("Özet")
cols = st.columns(4)
cols[0].metric("Analiz edilen yorum", len(sonuc))
for c, (_, satir) in zip(cols[1:], dagilim.iterrows()):
    c.metric(satir["Duygu"], int(satir["Adet"]), f"%{satir['Adet'] / len(sonuc) * 100:.1f}", delta_color="off")

st.subheader("Duygu Dağılımı")
g1, g2 = st.columns(2)
with g1:
    pasta = px.pie(dagilim, names="Duygu", values="Adet", color="Duygu", color_discrete_map=RENKLER, hole=0.45)
    pasta.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(pasta, use_container_width=True)
with g2:
    sutun_g = px.bar(dagilim, x="Duygu", y="Adet", color="Duygu", color_discrete_map=RENKLER, text="Adet")
    sutun_g.update_layout(showlegend=False, margin=dict(t=20, b=20))
    st.plotly_chart(sutun_g, use_container_width=True)

st.subheader("En Sık Kullanılan 15 Anlamlı Kelime")
kelimeler = sik_kelimeler(sonuc["Yorum"])
if kelimeler.empty:
    st.write("Gösterilecek kelime bulunamadı.")
else:
    kg = px.bar(kelimeler.iloc[::-1], x="Adet", y="Kelime", orientation="h", text="Adet")
    kg.update_traces(marker_color="#4c6ef5")
    kg.update_layout(margin=dict(t=20, b=20), height=480)
    st.plotly_chart(kg, use_container_width=True)

st.subheader("Olumsuz Yorumlar")
olumsuz = sonuc[sonuc["Duygu"] == "Olumsuz"][["Yorum", "Puan"]]
if olumsuz.empty:
    st.write("Olumsuz yorum bulunamadı.")
else:
    st.dataframe(olumsuz.reset_index(drop=True), use_container_width=True)

st.subheader("Sonuçları İndir")
indirilecek = sonuc.rename(columns={"Yorum": f"Yorum ({sutun})"})
st.download_button(
    "Sonuçları CSV olarak indir",
    data=indirilecek.to_csv(index=False).encode("utf-8-sig"),
    file_name="duygu_analizi_sonuclari.csv",
    mime="text/csv",
)
