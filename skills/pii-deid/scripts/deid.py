#!/usr/bin/env python3
"""pii-deid — Taiwan judgment PII redactor.

CLI:
    python3 skills/pii-deid/scripts/deid.py "<text>"
    cat samples/judgment_sample_001.txt | python3 skills/pii-deid/scripts/deid.py -

Importable:
    from skills.pii_deid.scripts.deid import deidentify
    deidentify(text) -> {"redacted": str, "map": {code: original}}
"""
from __future__ import annotations

import json
import re
import sys
from typing import Dict, Tuple

# --- Chinese name ---------------------------------------------------------
# Taiwan common surnames (百家姓 + frequent Taiwan surnames). A personal name
# in a judgment begins with one of these; the remaining 1-3 Han characters
# are the given name. This surname-anchored approach is far more precise than
# matching any 2-4 Han run after a role tag, which greedily swallows verb
# phrases like "因公共危" (被告因公共危險...) or "聲請以簡易".
SURNAMES = (
    "王李張劉陳楊黃趙周吳徐孫朱馬胡郭何高羅鄭梁謝宋唐許韓馮鄧曹彭曾"
    "蕭田董蔡潘袁蔣沈韋姜范江傅于石戴魏侯方金崔鍾譚陸汪范黎余葉廖"
    "呂范尤林詹蘇柯賴白丁游簡邱顧任柳秦管夏程朱康賀莫常卞倪聶席雷"
    "陶賈穆柴龔嚴孟涂童閻解巫邵翁費廉岑薛雷賀倪湯殷黎閔畢耿賈華宗"
    "屈向覃鮑計饒冷盧陸鄒魯阮藍鍾諸馬安時龐卓洪紀甯古全歐陽司馬諸葛"
    "司徒上官澹臺尉遲公孫軒轅宇文長孫單于鮮于聞人東方慕容司空"
    "艾卜巴包班暴貝畢邊卞冰別并邴薄"
    "蔡曹岑查柴常暢晁車成郝乘程池仇褚淳于慈從叢崔"
    "達戴鄧狄刁丁董都竇杜段段干端木多"
    "鄂樊范方費馮伏符傅鳳福封"
    "甘高皋郜戈葛弓公孫宮龔勾古谷顧關郭國"
    "海韓杭郝和賀赫連衡洪侯胡扈花華宦黃霍"
    "姬嵇計紀季籍賈兼簡翦姜蔣焦皎揭金靳井景景頗荊居鞠"
    "康柯空孔寇蒯匡況鄺"
    "藍郎勞老樂雷冷黎利厲連廉練梁廖林藺凌令狐劉柳龍隆婁樓盧魯陸鹿呂"
    "馬麥滿毛茅梅蒙孟糜米密苗閔繆莫墨牟木穆慕容"
    "那納乜倪聶寧牛鈕鈕祜祿女"
    "歐歐陽"
    "潘龐逢費皮平蒲溥濮浦朴漆蕭錢強喬秦邱仇裘曲屈瞿全"
    "饒冉壤駟任戎榮容茹阮芮"
    "薩賽桑沙啥尚少申沈盛師施石時史叔孫舒束帥雙水司空司馬司徒宋蘇宿粟隋孫索"
    "臺談覃唐陶滕鐵佟仝通童塗屠"
    "宛萬汪危韋衛魏問文聞翁烏鄔巫無吳伍武"
    "郗奚習席夏先冼鮮於顯相向項蕭謝辛忻莘邢熊修徐許宣薛荀"
    "嚴閻晏鄢燕楊仰陽堯葉衣伊易益尹銀印應英游尤于余虞禹郁喻遇元袁岳雲"
    "臧翟詹展張章湛招趙肇甄鄭支鍾週鄒祝朱諸朱葛竹竺祝左"
    "阿烏白巴卑"
)

# Unique the surname set — Python dict keeps insertion order but for a string
# we just collapse duplicates via dict.fromkeys.
SURNAMES = "".join(dict.fromkeys(SURNAMES))
# Remove rare single-character "surnames" that also function as common
# function words or place prefixes, which causes false positives:
#   於 (preposition "at/in"), 臺 (place prefix "Taiwan-"), 都 (adverb),
#   和 (conjunction), 方 (suffix "-square"), 中 (middle), 時 (time), 先
#   (prior), 單 (single), 達 (reach), 全 (all), 本 (this), 南 (south).
_REMOVE = "於臺都和方中時先單達全本南"
SURNAMES = "".join(c for c in SURNAMES if c not in _REMOVE)

# Characters that cannot be part of a given name — they signal the start of
# a verb / postposition / conjunction / place suffix. When the greedy-match
# regex hits one of these we know the name has ended.
NAME_STOP_CHARS = (
    "的了於在是有與而及或並為以所其於然本案件等之判聲明知駕承坦意"
    "請將已業應復經即不但又也則即再又則使令使得可而以然若則是否"
    "死傷重輕罪犯被其該此那或及與竊盜偷竊傷害妨害涉犯涉嫌所因於"
    "及第一二三四五六七八九十上下前後中外內間左右東西南北所是非"
    "地法檢分警派刑民交市縣簡公銀商事案部庭條長員轄政醫機審偵"
    "告上辯車事因明於坦為聲認"
)

# Name: a surname followed by 1-3 Han characters (given name). We use a lazy
# match but with an explicit negative-lookahead stop-set, so we pick the
# longest plausible name but stop before a verb / postposition.
NAME_GIVEN = rf"(?:(?![{NAME_STOP_CHARS}])[\u4e00-\u9fff]){{1,3}}"
NAME = rf"[{SURNAMES}]{NAME_GIVEN}"

# Compound surnames (歐陽, 司馬, 諸葛, 上官, ...) are already covered by the
# regex because the single-char prefix of the compound is itself in SURNAMES.
NOT_NAME_SUFFIX = (
    r"(?!地方|法院|檢察|分局|警察|派出|派遣|刑事|民事|交通|市政|縣政|簡易|"
    r"公司|銀行|商店|事件|案件|部分|法庭|法條|庭長|庭員|轄區|警局|政府|"
    r"醫院|機關|審判|偵查|告訴|上訴|辯護|車牌)"
)

ROLE_NAME_PATTERNS: list[tuple[str, str]] = [
    # (role_prefix, code_family)
    # Note: 聲請人 is excluded — it is almost always an institution
    # (the prosecutor's office), not a person. The actual prosecutor name is
    # reached via 檢察官 X later in the document.
    (r"被\s*告\s*人?", "D"),
    (r"被\s*害\s*人", "V"),
    (r"證\s*人", "W"),
    (r"檢\s*察\s*官", "O"),
    (r"法\s*官", "O"),
    (r"書\s*記\s*官", "O"),
    (r"辯\s*護\s*人", "O"),
    (r"告\s*訴\s*人", "V"),
]

# --- Structured PII -------------------------------------------------------
ROC_ID_RE = re.compile(r"(?<![A-Z])[A-Z][12]\d{8}(?!\d)")
# Vehicle plates. Taiwan formats: AAA-1234, 1234-AA, AB-1234, 123-4567 etc.
# We also explicitly handle masked ones like 000-0000. Restricted to the
# digits-first arm to avoid colliding with our own placeholder codes like
# `ADDR-001` or `PL-001`.
PLATE_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"\d{3,4}-[A-Z0-9]{3,4}"
    r"(?![A-Za-z0-9])"
)
# Phones: mobile 09xx-xxx-xxx, landline 0x-xxxxxxxx
PHONE_RE = re.compile(
    r"(?<!\d)(?:09\d{2}[- ]?\d{3}[- ]?\d{3}|0\d{1,2}[- ]?\d{6,8})(?!\d)"
)

# Taiwan address. Starts at a known city-name prefix (臺北市, 新北市, 桃園
# 市, 臺中市, 臺南市, 高雄市, 基隆市, 新竹市, 嘉義市, plus 縣s) — this is
# safer than trying to back-extend from 市 because many verbs end in a Han
# char that would otherwise get swallowed. Then optionally runs through
# 區/鄉/鎮, 村/里, 路/街/大道, 段, 巷, 弄, 號, 樓. Masked "○" are allowed
# inside. Whitespace (including line breaks and the page-column digit
# prefixes seen in our PDFs, e.g. "15 00巷00號") is tolerated between
# components.
_CITY = (
    r"(?:臺北|台北|新北|桃園|臺中|台中|臺南|台南|高雄|基隆|新竹|嘉義|"
    r"苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|臺東|台東|澎湖|金門|連江)"
    r"(?:縣|市)"
)
_WS = r"\s*(?:\n\s*\d{1,2}\s*)?"  # allow PDF page-col digit re-prefix
ADDR_RE = re.compile(
    rf"{_CITY}"
    rf"(?:{_WS}[\u4e00-\u9fff○]{{1,6}}(?:區|鄉|鎮|市))?"
    rf"(?:{_WS}[\u4e00-\u9fff○]{{1,8}}(?:村|里))?"
    rf"(?:{_WS}[\u4e00-\u9fff○\d]{{1,10}}(?:路|街|大道))"
    rf"(?:{_WS}[\u4e00-\u9fff○\d一二三四五六七八九十]{{1,4}}段)?"
    rf"(?:{_WS}\d+巷)?"
    rf"(?:{_WS}\d+弄)?"
    rf"(?:{_WS}\d+(?:之\d+)?號)"
    rf"(?:{_WS}\d+樓)?"
)


class _Assigner:
    """Hands out stable, zero-padded codes per family, in first-seen order."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}
        self._code_for: Dict[Tuple[str, str], str] = {}
        self.mapping: Dict[str, str] = {}

    def code(self, family: str, original: str) -> str:
        key = (family, original)
        if key in self._code_for:
            return self._code_for[key]
        n = self._counters.get(family, 0) + 1
        self._counters[family] = n
        code = f"{family}-{n:03d}"
        self._code_for[key] = code
        self.mapping[code] = original
        return code


def _apply_role_name_rules(text: str, assigner: _Assigner) -> str:
    """Replace `<role> <Chinese name>` occurrences with the right code family."""
    for role_re, family in ROLE_NAME_PATTERNS:
        pattern = re.compile(rf"({role_re})(\s*)({NAME}){NOT_NAME_SUFFIX}")

        def _sub(m: re.Match[str], fam: str = family) -> str:
            name = m.group(3)
            code = assigner.code(fam, name)
            return f"{m.group(1)}{m.group(2)}{code}"

        text = pattern.sub(_sub, text)
    return text


def _replay_known_names(text: str, assigner: _Assigner) -> str:
    """After role tagging, replace bare occurrences of already-known names."""
    known = [
        (orig, code)
        for code, orig in assigner.mapping.items()
        if re.fullmatch(NAME, orig)
    ]
    # Sort by length desc so longer names replace before shorter substrings.
    known.sort(key=lambda x: -len(x[0]))
    for orig, code in known:
        text = text.replace(orig, code)
    return text


def _apply_structured_rules(text: str, assigner: _Assigner) -> str:
    def _sub_factory(family: str):
        def _sub(m: re.Match[str]) -> str:
            return assigner.code(family, m.group(0))
        return _sub

    # Address must run before plate, because addresses may contain digits.
    text = ADDR_RE.sub(_sub_factory("ADDR"), text)
    text = ROC_ID_RE.sub(_sub_factory("ID"), text)
    text = PLATE_RE.sub(_sub_factory("PL"), text)
    text = PHONE_RE.sub(_sub_factory("PH"), text)
    return text


def deidentify(text: str) -> dict:
    """Replace Taiwan-specific PII in `text` with stable codes.

    Returns {"redacted": str, "map": {code: original}}.
    """
    if not isinstance(text, str):
        raise TypeError("deidentify expects str")

    assigner = _Assigner()
    redacted = _apply_role_name_rules(text, assigner)
    redacted = _replay_known_names(redacted, assigner)
    redacted = _apply_structured_rules(redacted, assigner)
    return {"redacted": redacted, "map": dict(assigner.mapping)}


def _read_cli_input(argv: list[str]) -> str:
    if len(argv) < 2 or argv[1] == "-":
        return sys.stdin.read()
    arg = argv[1]
    # Allow passing a path if it exists; otherwise treat as literal text.
    try:
        with open(arg, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, FileNotFoundError):
        return arg


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    text = _read_cli_input(argv)
    out = deidentify(text)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
