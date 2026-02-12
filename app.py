import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import csv
import datetime
import io
import re
import math
import time
from pdf_report import generate_report_pdf, generate_batch_summary_pdf

# ===== ページ設定 =====
st.set_page_config(page_title="企業デジタル分析ツール", page_icon="📊", layout="wide")

# ===== カスタムCSS =====
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700;900&display=swap');
.stApp { font-family: 'Noto Sans JP', sans-serif; }
.main-header { background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%); color: white; padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem; position: relative; overflow: hidden; }
.main-header::before { content: ''; position: absolute; top: -50%; right: -10%; width: 300px; height: 300px; background: radial-gradient(circle, rgba(56,189,248,0.15) 0%, transparent 70%); border-radius: 50%; }
.main-header h1 { font-size: 1.8rem; font-weight: 900; margin: 0 0 0.5rem 0; }
.main-header p { font-size: 0.95rem; color: #94a3b8; margin: 0; font-weight: 300; }
.score-card { background: white; border-radius: 16px; padding: 1.8rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; transition: transform 0.2s ease; }
.score-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
.score-card .score-label { font-size: 0.8rem; color: #64748b; font-weight: 500; letter-spacing: 0.08em; margin-bottom: 0.5rem; }
.score-card .score-value { font-size: 2.8rem; font-weight: 900; line-height: 1; margin-bottom: 0.3rem; }
.score-card .score-sub { font-size: 0.85rem; color: #94a3b8; }
.score-s { color: #dc2626; } .score-a { color: #ea580c; } .score-b { color: #d97706; } .score-c { color: #2563eb; } .score-d { color: #16a34a; }
.rank-badge { display: inline-block; font-size: 1.5rem; font-weight: 900; width: 56px; height: 56px; line-height: 56px; text-align: center; border-radius: 12px; margin-bottom: 0.5rem; }
.rank-s { background: linear-gradient(135deg, #fecaca, #fca5a5); color: #dc2626; }
.rank-a { background: linear-gradient(135deg, #fed7aa, #fdba74); color: #ea580c; }
.rank-b { background: linear-gradient(135deg, #fef08a, #fde047); color: #a16207; }
.rank-c { background: linear-gradient(135deg, #bfdbfe, #93c5fd); color: #2563eb; }
.rank-d { background: linear-gradient(135deg, #bbf7d0, #86efac); color: #16a34a; }
.analysis-item { background: white; border-radius: 12px; padding: 1.2rem 1.5rem; margin-bottom: 0.75rem; border: 1px solid #e2e8f0; display: flex; align-items: center; gap: 1rem; }
.analysis-item .item-icon { font-size: 1.3rem; width: 40px; text-align: center; flex-shrink: 0; }
.analysis-item .item-content { flex: 1; }
.analysis-item .item-name { font-size: 0.9rem; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
.analysis-item .item-bar-bg { background: #f1f5f9; height: 8px; border-radius: 4px; overflow: hidden; }
.analysis-item .item-bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
.bar-high { background: linear-gradient(90deg, #22c55e, #4ade80); }
.bar-mid { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.bar-low { background: linear-gradient(90deg, #ef4444, #f87171); }
.analysis-item .item-score { font-size: 0.95rem; font-weight: 700; color: #334155; flex-shrink: 0; min-width: 60px; text-align: right; }
.alert-target { background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 1px solid #fecaca; border-left: 4px solid #dc2626; color: #991b1b; padding: 1rem 1.5rem; border-radius: 0 12px 12px 0; font-weight: 500; margin: 1rem 0; }
.alert-maybe { background: linear-gradient(135deg, #fffbeb, #fef3c7); border: 1px solid #fde68a; border-left: 4px solid #d97706; color: #92400e; padding: 1rem 1.5rem; border-radius: 0 12px 12px 0; font-weight: 500; margin: 1rem 0; }
.alert-safe { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border: 1px solid #bbf7d0; border-left: 4px solid #16a34a; color: #166534; padding: 1rem 1.5rem; border-radius: 0 12px 12px 0; font-weight: 500; margin: 1rem 0; }
.detail-section { background: #f8fafc; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; border: 1px solid #e2e8f0; }
.detail-section h4 { font-size: 0.95rem; font-weight: 700; color: #1e293b; margin: 0 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e2e8f0; }
.detail-row { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #f1f5f9; font-size: 0.88rem; }
.detail-row:last-child { border-bottom: none; }
.detail-label { color: #64748b; } .detail-value { font-weight: 600; color: #1e293b; }
.check-ok { color: #16a34a; } .check-ng { color: #dc2626; }
.radar-container { display: flex; justify-content: center; margin: 1rem 0; }
.footer { text-align: center; color: #94a3b8; font-size: 0.8rem; padding: 2rem 0 1rem; border-top: 1px solid #e2e8f0; margin-top: 2rem; }
.stTextInput > div > div > input { border-radius: 12px; border: 2px solid #e2e8f0; padding: 0.75rem 1rem; font-size: 1rem; }
.stTextInput > div > div > input:focus { border-color: #38bdf8; box-shadow: 0 0 0 3px rgba(56,189,248,0.15); }
.stButton > button[kind="primary"] { border-radius: 12px; padding: 0.75rem 2rem; font-weight: 700; font-size: 1rem; background: linear-gradient(135deg, #0ea5e9, #0284c7); border: none; }
.stButton > button[kind="primary"]:hover { background: linear-gradient(135deg, #0284c7, #0369a1); }
.batch-summary { background: white; border-radius: 16px; padding: 1.5rem; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 1rem; }
.batch-summary .summary-number { font-size: 2rem; font-weight: 900; line-height: 1.2; }
.batch-summary .summary-label { font-size: 0.8rem; color: #64748b; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ===== 定数 =====
HEADERS_REQ = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT = 15
SNS_DOMAINS = {"twitter.com":"Twitter/X","x.com":"X","facebook.com":"Facebook","instagram.com":"Instagram","linkedin.com":"LinkedIn","youtube.com":"YouTube","tiktok.com":"TikTok","line.me":"LINE","note.com":"note"}
RECRUIT_KEYWORDS = ["recruit","career","careers","jobs","hiring","採用","求人","リクルート","新卒","中途","entry","joblist","employment"]
CATEGORY_KEYWORDS = {
    "製造":["製造","工場","製作所","メーカー","manufacturing","factory"],
    "IT・Web":["システム","ソフトウェア","IT","Web","アプリ","デジタル","tech"],
    "建設・不動産":["建設","建築","不動産","工務店","リフォーム","housing"],
    "飲食":["飲食","レストラン","食堂","カフェ","料理","food"],
    "小売":["販売","ショップ","ストア","store","shop","通販"],
    "医療・介護":["医療","クリニック","病院","介護","福祉","歯科"],
    "教育":["教育","学校","スクール","塾","学習","academy"],
    "士業":["税理士","会計士","弁護士","司法書士","行政書士","社労士"],
}
SCORE_META = [{"icon":"🔒"},{"icon":"🔍"},{"icon":"📱"},{"icon":"📄"},{"icon":"📞"},{"icon":"⚙️"},{"icon":"👥"}]

# ===== ユーティリティ =====
def normalize_url(url):
    url = url.strip()
    if not url: return ""
    if not url.startswith(("http://","https://")): url = "https://" + url
    if not urlparse(url).path: url += "/"
    return url

def get_page_safely(url):
    try:
        r = requests.get(url, headers=HEADERS_REQ, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        if r.encoding and r.encoding.lower() == "iso-8859-1": r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser"), None
    except requests.exceptions.ConnectionError: return None, "接続エラー"
    except requests.exceptions.Timeout: return None, "タイムアウト"
    except requests.exceptions.HTTPError as e: return None, f"HTTP {e.response.status_code}"
    except requests.exceptions.RequestException as e: return None, f"エラー: {str(e)[:80]}"

# ===== 分析関数群 =====
def check_https(url): return url.startswith("https://")

def analyze_meta_seo(soup):
    r = {"title":"","title_length":0,"description":"","description_length":0,"has_viewport":False,"has_ogp":False,"h1_count":0,"h1_text":"","has_favicon":False,"has_canonical":False}
    t = soup.find("title")
    if t and t.string: r["title"]=t.string.strip(); r["title_length"]=len(r["title"])
    d = soup.find("meta",attrs={"name":"description"})
    if d and d.get("content"): r["description"]=d["content"].strip(); r["description_length"]=len(r["description"])
    r["has_viewport"] = soup.find("meta",attrs={"name":"viewport"}) is not None
    r["has_ogp"] = soup.find("meta",attrs={"property":"og:title"}) is not None
    h1s = soup.find_all("h1"); r["h1_count"]=len(h1s)
    if h1s: r["h1_text"]=h1s[0].get_text(strip=True)[:50]
    r["has_favicon"] = soup.find("link",rel=lambda x:x and "icon" in x) is not None
    r["has_canonical"] = soup.find("link",rel="canonical") is not None
    return r

def analyze_links(soup, base_url):
    all_a = soup.find_all("a",href=True); bd = urlparse(base_url).netloc
    il,el,sns,rf,ru = [],[],{},False,""
    for a in all_a:
        h = a.get("href","").strip()
        if not h or h.startswith(("#","javascript:","mailto:","tel:")): continue
        fu = urljoin(base_url,h); ld = urlparse(fu).netloc.lower()
        if ld==bd or not ld: il.append(fu)
        else: el.append(fu)
        for sd,sn in SNS_DOMAINS.items():
            if sd in ld: sns[sn]=fu; break
        hl,tl = h.lower(), a.get_text(strip=True).lower()
        for kw in RECRUIT_KEYWORDS:
            if kw in hl or kw in tl: rf=True; ru=fu; break
    return {"total_links":len(all_a),"internal_links":len(il),"external_links":len(el),"sns_links":sns,"sns_count":len(sns),"recruit_found":rf,"recruit_url":ru}

def analyze_contact(soup):
    r = {"has_form":False,"has_phone":False,"phone_number":"","has_email_link":False,"has_contact_page":False}
    r["has_form"] = soup.find("form") is not None
    ph = re.findall(r"0\d{1,4}[-‐ー]?\d{1,4}[-‐ー]?\d{3,4}", soup.get_text())
    if ph: r["has_phone"]=True; r["phone_number"]=ph[0]
    r["has_email_link"] = soup.find("a",href=re.compile(r"^mailto:")) is not None
    for a in soup.find_all("a",href=True):
        ht = (a.get("href","")+a.get_text()).lower()
        if any(w in ht for w in ["問い合わせ","お問合せ","contact","inquiry"]): r["has_contact_page"]=True; break
    return r

def detect_category(soup):
    text = soup.get_text().lower(); sc = {}
    for c,kws in CATEGORY_KEYWORDS.items():
        n = sum(1 for k in kws if k.lower() in text)
        if n>0: sc[c]=n
    return max(sc,key=sc.get) if sc else "その他"

def analyze_tech(soup):
    r = {"has_analytics":False,"has_structured_data":False,"image_count":0,"images_without_alt":0}
    ht = str(soup)
    if any(w in ht for w in ["google-analytics","gtag","googletagmanager"]): r["has_analytics"]=True
    if soup.find("script",type="application/ld+json"): r["has_structured_data"]=True
    imgs = soup.find_all("img"); r["image_count"]=len(imgs)
    r["images_without_alt"] = sum(1 for i in imgs if not i.get("alt"))
    return r

# ===== スコアリング =====
def calculate_score(url, seo, links, contact, tech):
    score=0; details=[]
    p=10 if check_https(url) else 0; score+=p; details.append(("HTTPS対応",p,10,"✅" if p==10 else "❌"))
    s=0
    if 10<=seo["title_length"]<=60: s+=8
    elif seo["title_length"]>0: s+=4
    if 50<=seo["description_length"]<=160: s+=7
    elif seo["description_length"]>0: s+=3
    if seo["has_viewport"]: s+=5
    if seo["h1_count"]==1: s+=3
    elif seo["h1_count"]>1: s+=1
    if seo["has_favicon"]: s+=2
    score+=s; details.append(("SEO基礎",s,25,"✅" if s>=18 else("⚠️" if s>=10 else "❌")))
    s=min(links["sns_count"]*5,15); score+=s; details.append(("SNS連携",s,15,"✅" if s>=10 else("⚠️" if s>=5 else "❌")))
    s=0
    if links["total_links"]>100: s+=10
    elif links["total_links"]>50: s+=7
    elif links["total_links"]>20: s+=4
    if links["internal_links"]>30: s+=5
    elif links["internal_links"]>10: s+=3
    s=min(s,15); score+=s; details.append(("コンテンツ充実度",s,15,"✅" if s>=10 else("⚠️" if s>=5 else "❌")))
    s=0
    if contact["has_form"]: s+=6
    if contact["has_phone"]: s+=4
    if contact["has_email_link"]: s+=3
    if contact["has_contact_page"]: s+=2
    s=min(s,15); score+=s; details.append(("問い合わせ導線",s,15,"✅" if s>=10 else("⚠️" if s>=5 else "❌")))
    s=0
    if tech["has_analytics"]: s+=5
    if tech["has_structured_data"]: s+=3
    if seo["has_ogp"]: s+=2
    s=min(s,10); score+=s; details.append(("技術・運用",s,10,"✅" if s>=7 else("⚠️" if s>=3 else "❌")))
    p=10 if links["recruit_found"] else 0; score+=p; details.append(("採用ページ",p,10,"✅" if p==10 else "❌"))
    return score, details

def judge(score):
    if score<=25: return "S","最優先ターゲット","s"
    elif score<=40: return "A","営業対象（高確度）","a"
    elif score<=55: return "B","営業対象（中確度）","b"
    elif score<=70: return "C","要検討","c"
    else: return "D","対象外（デジタル成熟）","d"

# ===== SVGレーダーチャート =====
def radar_svg(details):
    cats = [{"name":n.replace("コンテンツ充実度","コンテンツ").replace("問い合わせ導線","問い合わせ"),"pct":p/m if m>0 else 0} for n,p,m,_ in details]
    n=len(cats); cx,cy,rm=160,160,120; off=-math.pi/2
    grid=""; axes=""; labels=""; pts=[]; dots=""
    for lv in [0.25,0.5,0.75,1.0]:
        grid+=f'<circle cx="{cx}" cy="{cy}" r="{rm*lv}" fill="none" stroke="#e2e8f0" stroke-width="1"/>'
    for i,c in enumerate(cats):
        a=off+(2*math.pi*i/n); x2=cx+rm*math.cos(a); y2=cy+rm*math.sin(a)
        axes+=f'<line x1="{cx}" y1="{cy}" x2="{x2}" y2="{y2}" stroke="#cbd5e1" stroke-width="1"/>'
        lr=rm+28; lx=cx+lr*math.cos(a); ly=cy+lr*math.sin(a)
        anc="middle"
        if math.cos(a)>0.3: anc="start"
        elif math.cos(a)<-0.3: anc="end"
        labels+=f'<text x="{lx}" y="{ly}" text-anchor="{anc}" dominant-baseline="central" fill="#475569" font-size="11" font-weight="500">{c["name"]}</text>'
        r=rm*c["pct"]; x=cx+r*math.cos(a); y=cy+r*math.sin(a)
        pts.append(f"{x},{y}")
        dots+=f'<circle cx="{x}" cy="{y}" r="4" fill="#0ea5e9" stroke="white" stroke-width="2"/>'
    return f'<svg viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg" style="max-width:320px;margin:auto;display:block;">{grid}{axes}<polygon points="{" ".join(pts)}" fill="rgba(14,165,233,0.15)" stroke="#0ea5e9" stroke-width="2.5"/>{dots}{labels}</svg>'

# ===== メイン分析 =====
def run_analysis(url):
    url=normalize_url(url)
    if not url: return None,"URLを入力してください"
    soup,err=get_page_safely(url)
    if err: return None,err
    seo=analyze_meta_seo(soup); lnk=analyze_links(soup,url); cnt=analyze_contact(soup)
    tch=analyze_tech(soup); cat=detect_category(soup); sc,det=calculate_score(url,seo,lnk,cnt,tch)
    rk,rl,rc=judge(sc)
    return {"url":url,"domain":urlparse(url).netloc,"score":sc,"rank":rk,"rank_label":rl,"rank_class":rc,"details":det,"seo":seo,"links":lnk,"contact":cnt,"tech":tch,"category":cat,"analyzed_at":datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},None

# ===== CSV生成（共通） =====
def generate_csv(results):
    buf = io.StringIO()
    fn = ["分析日時","URL","スコア","ランク","判定","業種","HTTPS","タイトル","description","viewport","OGP","H1数","リンク総数","内部","外部","SNS数","SNS一覧","採用","フォーム","電話","メール","Analytics","構造化データ","画像数","alt未設定"]
    w = csv.DictWriter(buf, fieldnames=fn); w.writeheader()
    for r in results:
        w.writerow({
            "分析日時":r["analyzed_at"],"URL":r["url"],"スコア":r["score"],"ランク":r["rank"],
            "判定":r["rank_label"],"業種":r["category"],
            "HTTPS":"○" if check_https(r["url"]) else "×","タイトル":r["seo"]["title"],
            "description":"○" if r["seo"]["description_length"]>0 else "×",
            "viewport":"○" if r["seo"]["has_viewport"] else "×",
            "OGP":"○" if r["seo"]["has_ogp"] else "×","H1数":r["seo"]["h1_count"],
            "リンク総数":r["links"]["total_links"],"内部":r["links"]["internal_links"],
            "外部":r["links"]["external_links"],"SNS数":r["links"]["sns_count"],
            "SNS一覧":" / ".join(r["links"]["sns_links"].keys()),
            "採用":"○" if r["links"]["recruit_found"] else "×",
            "フォーム":"○" if r["contact"]["has_form"] else "×","電話":r["contact"]["phone_number"],
            "メール":"○" if r["contact"]["has_email_link"] else "×",
            "Analytics":"○" if r["tech"]["has_analytics"] else "×",
            "構造化データ":"○" if r["tech"]["has_structured_data"] else "×",
            "画像数":r["tech"]["image_count"],"alt未設定":r["tech"]["images_without_alt"],
        })
    return buf.getvalue()

# ===== セッション =====
if "results_history" not in st.session_state: st.session_state.results_history=[]
if "batch_results" not in st.session_state: st.session_state.batch_results=[]

# ============================================
#           サイドバー（モード切替）
# ============================================
with st.sidebar:
    st.markdown("### ⚙️ モード選択")
    mode = st.radio("分析モード", ["🔍 単体分析", "📋 一括分析"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("#### 📖 使い方")
    if "単体" in mode:
        st.markdown("1. URLを入力\n2. 「分析する」をクリック\n3. 結果を確認・CSV保存")
    else:
        st.markdown("1. URLを入力欄に貼り付け\n　（1行1URL）\n2. またはCSVアップロード\n3. 「一括分析」をクリック\n4. 結果をCSVダウンロード")
    st.markdown("---")
    st.markdown(f"**分析済み:** {len(st.session_state.results_history)}件")

# ============================================
#               ヘッダー
# ============================================
st.markdown("""
<div class="main-header">
    <h1>📊 企業デジタル分析ツール</h1>
    <p>Webサイトのデジタル成熟度を7項目100点満点でスコアリング。スコアが低い企業ほどWeb改善の営業対象候補になります。</p>
</div>
""", unsafe_allow_html=True)

# ============================================
#            単体分析モード
# ============================================
if "単体" in mode:
    ci,cb=st.columns([4,1])
    with ci: url=st.text_input("URL",placeholder="https://example.co.jp",label_visibility="collapsed")
    with cb: clicked=st.button("🔍 分析する",type="primary",use_container_width=True)

    if clicked and url:
        with st.spinner("分析中..."):
            result,error=run_analysis(url)
        if error:
            st.markdown(f'<div class="alert-target">⚠️ {error}</div>',unsafe_allow_html=True)
        else:
            st.session_state.results_history.append(result)
            sc=result["score"]; rk=result["rank"]; rc=result["rank_class"]
            st.markdown("<br>",unsafe_allow_html=True)

            c1,c2,c3=st.columns(3)
            with c1: st.markdown(f'<div class="score-card"><div class="score-label">総合スコア</div><div class="score-value score-{rc}">{sc}</div><div class="score-sub">/ 100点</div></div>',unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="score-card"><div class="score-label">営業ランク</div><div class="rank-badge rank-{rc}">{rk}</div><div class="score-sub">{result["rank_label"]}</div></div>',unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="score-card"><div class="score-label">推定業種</div><div class="score-value" style="font-size:1.6rem;color:#1e293b;">{result["category"]}</div><div class="score-sub">{result["domain"]}</div></div>',unsafe_allow_html=True)

            if sc<=40: st.markdown(f'<div class="alert-target">🎯 <strong>営業対象です！</strong> スコア{sc}点 → Web改善の提案余地が大きい企業です</div>',unsafe_allow_html=True)
            elif sc<=55: st.markdown(f'<div class="alert-maybe">⚠️ <strong>要検討</strong> スコア{sc}点 → 部分的に改善提案が可能です</div>',unsafe_allow_html=True)
            else: st.markdown(f'<div class="alert-safe">✅ <strong>対象外</strong> スコア{sc}点 → デジタル施策が充実しています</div>',unsafe_allow_html=True)

            st.markdown("<br>",unsafe_allow_html=True)
            cr,ci2=st.columns([1,1])
            with cr:
                st.markdown("#### 📈 スコアレーダー")
                st.markdown(f'<div class="radar-container">{radar_svg(result["details"])}</div>',unsafe_allow_html=True)
            with ci2:
                st.markdown("#### 📋 スコア内訳")
                for i,(nm,pts,mx,_) in enumerate(result["details"]):
                    pct=int(pts/mx*100) if mx>0 else 0
                    bc="bar-high" if pct>=70 else("bar-mid" if pct>=40 else "bar-low")
                    st.markdown(f'<div class="analysis-item"><div class="item-icon">{SCORE_META[i]["icon"]}</div><div class="item-content"><div class="item-name">{nm}</div><div class="item-bar-bg"><div class="item-bar-fill {bc}" style="width:{pct}%"></div></div></div><div class="item-score">{pts}/{mx}</div></div>',unsafe_allow_html=True)

            st.markdown("<br>",unsafe_allow_html=True)
            d1,d2=st.columns(2)
            with d1:
                se=result["seo"]
                st.markdown(f"""<div class="detail-section"><h4>🔍 SEO分析</h4>
                <div class="detail-row"><span class="detail-label">タイトル</span><span class="detail-value">{se['title'][:40] or '（なし）'}（{se['title_length']}文字）</span></div>
                <div class="detail-row"><span class="detail-label">meta description</span><span class="detail-value">{'✅あり' if se['description_length']>0 else '❌なし'}（{se['description_length']}文字）</span></div>
                <div class="detail-row"><span class="detail-label">モバイル対応</span><span class="detail-value check-{'ok' if se['has_viewport'] else 'ng'}">{'✅対応' if se['has_viewport'] else '❌未対応'}</span></div>
                <div class="detail-row"><span class="detail-label">OGP</span><span class="detail-value check-{'ok' if se['has_ogp'] else 'ng'}">{'✅あり' if se['has_ogp'] else '❌なし'}</span></div>
                <div class="detail-row"><span class="detail-label">H1タグ</span><span class="detail-value">{se['h1_count']}個</span></div>
                <div class="detail-row"><span class="detail-label">canonical</span><span class="detail-value check-{'ok' if se['has_canonical'] else 'ng'}">{'✅あり' if se['has_canonical'] else '❌なし'}</span></div>
                <div class="detail-row"><span class="detail-label">favicon</span><span class="detail-value check-{'ok' if se['has_favicon'] else 'ng'}">{'✅あり' if se['has_favicon'] else '❌なし'}</span></div>
                </div>""",unsafe_allow_html=True)
                tc=result["tech"]; ar=int((tc["image_count"]-tc["images_without_alt"])/tc["image_count"]*100) if tc["image_count"]>0 else 0
                st.markdown(f"""<div class="detail-section"><h4>⚙️ 技術・運用</h4>
                <div class="detail-row"><span class="detail-label">Google Analytics</span><span class="detail-value check-{'ok' if tc['has_analytics'] else 'ng'}">{'✅導入済み' if tc['has_analytics'] else '❌未導入'}</span></div>
                <div class="detail-row"><span class="detail-label">構造化データ</span><span class="detail-value check-{'ok' if tc['has_structured_data'] else 'ng'}">{'✅あり' if tc['has_structured_data'] else '❌なし'}</span></div>
                <div class="detail-row"><span class="detail-label">画像数</span><span class="detail-value">{tc['image_count']}枚</span></div>
                <div class="detail-row"><span class="detail-label">alt属性</span><span class="detail-value">{ar}%設定済み</span></div>
                </div>""",unsafe_allow_html=True)
            with d2:
                lk=result["links"]; sh=""
                if lk["sns_links"]:
                    for nm2,_ in lk["sns_links"].items(): sh+=f'<div class="detail-row"><span class="detail-label">{nm2}</span><span class="detail-value check-ok">✅連携</span></div>'
                else: sh='<div class="detail-row"><span class="detail-label">SNS</span><span class="detail-value check-ng">❌見つからず</span></div>'
                st.markdown(f"""<div class="detail-section"><h4>🔗 リンク構造</h4>
                <div class="detail-row"><span class="detail-label">総リンク数</span><span class="detail-value">{lk['total_links']}</span></div>
                <div class="detail-row"><span class="detail-label">内部リンク</span><span class="detail-value">{lk['internal_links']}</span></div>
                <div class="detail-row"><span class="detail-label">外部リンク</span><span class="detail-value">{lk['external_links']}</span></div>
                {sh}
                <div class="detail-row"><span class="detail-label">採用ページ</span><span class="detail-value check-{'ok' if lk['recruit_found'] else 'ng'}">{'✅あり' if lk['recruit_found'] else '❌なし'}</span></div>
                </div>""",unsafe_allow_html=True)
                ct2=result["contact"]
                st.markdown(f"""<div class="detail-section"><h4>📞 問い合わせ導線</h4>
                <div class="detail-row"><span class="detail-label">フォーム</span><span class="detail-value check-{'ok' if ct2['has_form'] else 'ng'}">{'✅あり' if ct2['has_form'] else '❌なし'}</span></div>
                <div class="detail-row"><span class="detail-label">電話番号</span><span class="detail-value check-{'ok' if ct2['has_phone'] else 'ng'}">{'✅'+ct2['phone_number'] if ct2['has_phone'] else '❌見つからず'}</span></div>
                <div class="detail-row"><span class="detail-label">メール</span><span class="detail-value check-{'ok' if ct2['has_email_link'] else 'ng'}">{'✅あり' if ct2['has_email_link'] else '❌なし'}</span></div>
                <div class="detail-row"><span class="detail-label">問い合わせページ</span><span class="detail-value check-{'ok' if ct2['has_contact_page'] else 'ng'}">{'✅あり' if ct2['has_contact_page'] else '❌なし'}</span></div>
                </div>""",unsafe_allow_html=True)

            # --- PDFレポートダウンロード ---
            st.markdown("<br>",unsafe_allow_html=True)
            try:
                pdf_bytes = generate_report_pdf(result)
                st.download_button(
                    "📄 PDFレポートをダウンロード",
                    data=pdf_bytes,
                    file_name=f"report_{result['domain']}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"PDF生成でエラーが発生しました: {e}")
                st.caption("💡 reportlab が必要です: pip install reportlab")

# ============================================
#            一括分析モード
# ============================================
elif "一括" in mode:
    st.markdown("### 📋 一括分析")
    st.markdown("複数の企業URLをまとめて分析します。1行に1URLを入力してください。")

    # 入力方法の選択
    input_method = st.radio("入力方法", ["📝 テキスト入力", "📁 CSVアップロード"], horizontal=True, label_visibility="collapsed")

    urls_to_analyze = []

    if "テキスト" in input_method:
        url_text = st.text_area(
            "URLリスト（1行1URL）",
            height=200,
            placeholder="https://example1.co.jp\nhttps://example2.co.jp\nhttps://example3.co.jp"
        )
        if url_text:
            urls_to_analyze = [u.strip() for u in url_text.strip().split("\n") if u.strip()]

    else:
        uploaded = st.file_uploader("URLが含まれるCSVファイル", type=["csv","txt"])
        if uploaded:
            content = uploaded.read().decode("utf-8-sig")
            lines = content.strip().split("\n")
            for line in lines:
                # CSVの各列をチェック、URLっぽいものを抽出
                for cell in line.split(","):
                    cell = cell.strip().strip('"')
                    if cell.startswith(("http://","https://")) or "." in cell:
                        if any(cell.endswith(d) or d+"/" in cell for d in [".jp",".com",".co.jp",".net",".org",".io"]) or cell.startswith("http"):
                            urls_to_analyze.append(cell)
                            break

    if urls_to_analyze:
        st.info(f"📊 {len(urls_to_analyze)} 件のURLが入力されています")

        # 待ち時間の目安
        wait_sec = len(urls_to_analyze) * 5
        st.caption(f"⏱ 推定所要時間: 約{wait_sec//60}分{wait_sec%60}秒（1件あたり約5秒）")

    batch_clicked = st.button("🚀 一括分析を開始", type="primary", use_container_width=True, disabled=len(urls_to_analyze)==0)

    if batch_clicked and urls_to_analyze:
        st.session_state.batch_results = []
        errors = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.empty()

        for i, u in enumerate(urls_to_analyze):
            status_text.markdown(f"**分析中:** {u} （{i+1}/{len(urls_to_analyze)}）")
            progress_bar.progress((i) / len(urls_to_analyze))

            result, error = run_analysis(u)
            if error:
                errors.append({"url": u, "error": error})
            else:
                st.session_state.batch_results.append(result)
                st.session_state.results_history.append(result)

            # サーバー負荷軽減のための待機
            if i < len(urls_to_analyze) - 1:
                time.sleep(1)

        progress_bar.progress(1.0)
        status_text.markdown("**✅ 分析完了！**")

        if errors:
            st.warning(f"⚠️ {len(errors)}件のエラーが発生しました")
            with st.expander("エラー詳細"):
                for e in errors:
                    st.write(f"- {e['url']}: {e['error']}")

    # 一括分析結果の表示
    if st.session_state.batch_results:
        br = st.session_state.batch_results
        st.markdown("---")
        st.markdown(f"### 📊 一括分析結果（{len(br)}件）")

        # サマリーカード
        targets = [r for r in br if r["score"] <= 40]
        maybes = [r for r in br if 40 < r["score"] <= 55]
        safes = [r for r in br if r["score"] > 55]
        avg_score = sum(r["score"] for r in br) / len(br) if br else 0

        s1,s2,s3,s4 = st.columns(4)
        with s1:
            st.markdown(f'<div class="batch-summary" style="text-align:center;"><div class="summary-number" style="color:#dc2626;">{len(targets)}</div><div class="summary-label">🎯 営業対象</div></div>',unsafe_allow_html=True)
        with s2:
            st.markdown(f'<div class="batch-summary" style="text-align:center;"><div class="summary-number" style="color:#d97706;">{len(maybes)}</div><div class="summary-label">⚠️ 要検討</div></div>',unsafe_allow_html=True)
        with s3:
            st.markdown(f'<div class="batch-summary" style="text-align:center;"><div class="summary-number" style="color:#16a34a;">{len(safes)}</div><div class="summary-label">✅ 対象外</div></div>',unsafe_allow_html=True)
        with s4:
            st.markdown(f'<div class="batch-summary" style="text-align:center;"><div class="summary-number" style="color:#2563eb;">{avg_score:.0f}</div><div class="summary-label">📊 平均スコア</div></div>',unsafe_allow_html=True)

        # 結果テーブル（スコア昇順＝営業対象が上）
        sorted_results = sorted(br, key=lambda x: x["score"])
        table_data = []
        for r in sorted_results:
            table_data.append({
                "ランク": r["rank"],
                "スコア": r["score"],
                "URL": r["domain"],
                "判定": r["rank_label"],
                "業種": r["category"],
                "HTTPS": "✅" if check_https(r["url"]) else "❌",
                "SNS": r["links"]["sns_count"],
                "採用": "✅" if r["links"]["recruit_found"] else "❌",
                "電話": "✅" if r["contact"]["has_phone"] else "❌",
            })
        st.dataframe(table_data, use_container_width=True, hide_index=True)

        # CSVダウンロード
        csv_data = generate_csv(sorted_results)
        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "📥 CSVダウンロード",
                data=csv_data,
                file_name=f"batch_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )
        with dl2:
            try:
                batch_pdf = generate_batch_summary_pdf(sorted_results)
                st.download_button(
                    "📄 PDFサマリーダウンロード",
                    data=batch_pdf,
                    file_name=f"batch_summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"PDF生成エラー: {e}")

        if st.button("🗑️ 一括分析結果をクリア"):
            st.session_state.batch_results = []
            st.rerun()

# ============================================
#         履歴（単体分析モード時のみ）
# ============================================
if "単体" in mode and st.session_state.results_history:
    st.markdown("<br>",unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(f"### 📁 分析履歴（{len(st.session_state.results_history)}件）")
    hd = [{"日時":r["analyzed_at"],"URL":r["domain"],"スコア":r["score"],"ランク":r["rank"],"判定":r["rank_label"],"業種":r["category"],"SNS":r["links"]["sns_count"],"採用":"✅" if r["links"]["recruit_found"] else "❌"} for r in st.session_state.results_history]
    st.dataframe(hd, use_container_width=True, hide_index=True)
    csv_data = generate_csv(st.session_state.results_history)
    cd,cc = st.columns([1,1])
    with cd:
        st.download_button("📥 CSVダウンロード", data=csv_data,
            file_name=f"analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv", type="primary", use_container_width=True)
    with cc:
        if st.button("🗑️ 履歴をクリア", use_container_width=True):
            st.session_state.results_history = []
            st.rerun()

# フッター
st.markdown('<div class="footer">企業デジタル分析ツール v4.0 | Built with Streamlit + Python</div>', unsafe_allow_html=True)
