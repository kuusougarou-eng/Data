from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

from src.core.config import config

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - runtime dependency
    ChatOpenAI = None  # type: ignore
    HumanMessage = None  # type: ignore
    SystemMessage = None  # type: ignore


Layer1SlideType = Literal[
    "opening",
    "agenda",
    "divider",
    "content_pptx",
    "content_fullimage",
    "disclaimer",
    "closer",
]

Layer1LogicType = Literal[
    "comparison",
    "hierarchy",
    "process",
    "matrix",
    "layered_model",
    "before_after",
    "decision",
    "issue_split",
    "case_analysis",
    "phased_plan",
    "rationale",
    "positioning",
    "operating_policy",
]


class Layer1BodyComponent(BaseModel):
    """Layer2 が図解化に使う論理構造の部品。"""

    function: str = Field(
        ...,
        description=(
            "logic_type内での意味役割。例: problem_state, mechanism, "
            "operational_implication, option, criterion, layer, step, state, "
            "decision_criterion, issue, case, phase, principle, role, policy."
        ),
    )
    heading: str = Field(
        ...,
        description="元記事の見出しではなく、このcomponentの論理役割を表す短い見出し。",
    )
    content: str = Field(
        ...,
        description="2〜3文。入力由来の固有名詞・数値・条件・比較軸・代表例を含む。",
    )

    @field_validator("function", "heading", "content")
    @classmethod
    def _strip_component_text(cls, value: str) -> str:
        return (value or "").strip()


class Layer1BodyStructure(BaseModel):
    """Slide body の論理型。下流検査用の補助情報。"""

    page_role: str = Field(
        "",
        description="デッキ全体におけるこのページ固有の役割。例: 起点, 転換点, 構造, 比較, 判断, 次アクション。",
    )
    question: str = Field(
        "",
        description="このページが答える問い。title, leading_message, body_content はこの問いに揃える。",
    )
    logic_type: Layer1LogicType = Field(
        "comparison",
        description=(
            "ページ全体の論理型。comparison, hierarchy, process, matrix, layered_model, "
            "before_after, decision, issue_split, case_analysis, phased_plan, rationale, "
            "positioning, operating_policy から選ぶ。causal_chain は使わない。"
        ),
    )
    thesis: str = Field(
        "",
        description=(
            "leading_message と同一の文を設定する（Layer2 図解化の参照用）。"
            "questionへの直接回答を普通体・平文で書いた1文（動詞終止形可）。"
        ),
    )
    handoff_to_next: str = Field(
        "",
        description=(
            "このスライドの結論を受けて、次スライドで立てるべき問い（1文）。"
            "Closingスライドでは空でよい。"
            "例: 「ではどの案件類型から着手すべきか」"
        ),
    )
    components: List[Layer1BodyComponent] = Field(
        default_factory=list,
        description="補助参照用。空でよい。",
    )

    @field_validator("page_role", "question", "thesis", "handoff_to_next")
    @classmethod
    def _strip_structure_text(cls, value: str) -> str:
        return (value or "").strip()


class Layer1Slide(BaseModel):
    """Layer1 の最小出力単位。下流へ渡す意味構造だけを保持する。"""

    slide_type: Layer1SlideType = Field(
        ...,
        description=(
            "スライドの役割種別。opening, agenda, divider, content_pptx, "
            "content_fullimage, disclaimer, closer のいずれか。"
        ),
    )
    title: str = Field(
        ...,
        description="スライドのタイトル",
    )
    leading_message: str = Field(
        ...,
        description=(
            "questionへの直接回答を普通体・平文で書いた1文（動詞終止形可）。thesis と同一内容。"
            "読み手が反論できる具体的な主張として書くこと（反論不能な自明の文は機能しない）。"
            "LMはBodyの要約でも予告でもない。Bodyを読まなくてもLMの主張は完結していること。"
            "入力由来の固有名詞・数値・条件・比較軸・代表例を含め、主張の密度を出す。"
            "例: 「業務問いを起点にThin Sliceで小さく始めることが意味統合の現実的な進め方だ」"
        ),
    )
    body_content: str = Field(
        ...,
        description=(
            "LMを支持し、読み手がLMに従って動ける詳細説明。page_roleに応じた構成をとること。"
            "見出し・箇条書きなしの散文。入力由来の固有名詞・システム名・数値・代表例を織り込む。"
        ),
    )
    body_structure: Layer1BodyStructure = Field(
        default_factory=Layer1BodyStructure,
        description="Layer2が図解化するための論理構造。body_contentより優先して参照される。",
    )

    @field_validator("title", "leading_message", "body_content")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return (value or "").strip()


Layer1DeckType = Literal[
    "proposal",         # 提案書
    "report",           # 報告書
    "progress_report",  # 中間報告
    "discussion_paper", # DiscussionPaper
    "explanatory",      # 説明資料
    "strategy",         # 戦略資料
    "retrospective",    # 評価・振り返り
]


class Layer1Deck(BaseModel):
    """Layer1 の deck 出力。"""

    deck_type: Layer1DeckType = Field(
        ...,
        description=(
            "この資料の文書種別。enriched_promptの文書種別フィールドから設定する。"
            "proposal=提案書, report=報告書, progress_report=中間報告, "
            "discussion_paper=DiscussionPaper, explanatory=説明資料, "
            "strategy=戦略資料, retrospective=評価・振り返り。"
        ),
    )
    core_claim: str = Field(
        ...,
        description=(
            "このデッキが主張する単一の論証を普通体1文で書く（動詞終止形可）。"
            "全スライドのLMはこのcore_claimを支えるように設計されているはずである。"
            "読み手が反論できる具体的な主張であること。"
            "例: 「汎用AIツール試行が定着しない根本原因は業務フローへの組み込み設計の欠如であり、"
            "AI Agentによるフロー内自律実行がその唯一の解だ」"
        ),
    )
    slides: List[Layer1Slide] = Field(..., min_length=1, description="スライドの順序付き配列。")


LAYER1_SYSTEM_PROMPT_JA = """あなたはスライド生成システムの Layer 1: Narrative & Composition Layer。

# Role
enriched_prompt から Layer1Deck を生成する。各スライドは1つの問いに答え、スライドの連鎖が単一の論証を形成するデッキを設計する。

# Goal
core_claim（読み手が反論できる具体的な1文）を定め、全スライドの leading_message がそれを支える論証として積み上がる Layer1Deck を返す。スライドの集合ではなく、1つの論証の完成体。

デッキの最終目的は読み手の認識を変化させることである。文書種別ごとの変化ゴール:
- 提案書: 「この解決策以外に選択肢はない」と感じさせる
- 報告書: 「現状を正確に理解し、次アクションを判断できる」状態を作る
- 中間報告: 「現在地と残課題が明確になり、Go/No-Goの根拠が揃う」状態を作る
- DiscussionPaper: 「議論すべき問いの構造が明確になり、全員が同じ土台に立つ」状態を作る
- 説明資料: 「新しい概念の位置づけと適用範囲が分かる」状態を作る
- 戦略資料: 「優先順位と判断軸が共有され、実行の起点を揃えられる」状態を作る
- 評価・振り返り: 「何が機能し何が失敗したかの共通認識と、次回への含意が得られる」状態を作る

# Input
enriched_prompt には以下のフィールドが含まれる場合がある:
- 核心主張: このデッキが証明すべき論証ゴール。全スライドの LM はこれを支える設計にする
- 読み手の初期状態: Opening の LM で更新すべき認識（その認識の何が問題かを示す）
- 読み手の終着点: Closing の LM が指し示すべき判断・行動
- なぜ今: Opening の LM に「今この問いが立つ理由」として織り込む
- 文書種別: 後述の構成弱ルールの適用に使う
- 枚数: 生成するスライド数の上限

# Deck Structure
Opening（開口部）: 読み手がこの資料全体を評価するための視点・軸・問いを先に渡す。要約（内容の繰り返し）でも予告（何を扱うかの告知）でもない。
  - 提案書: 提案を必要とする問題の核心。解決策・条件・根拠はBodyに任せる
  - 説明資料: この資料が答える中心問いと分析軸。各軸の展開はBodyに任せる
  - DiscussionPaper: 合意すべき論点の構造。各論点の詳細はBodyに任せる
  - 中間報告: 現在どの状況にいるか。確認済み・未解決・計画はBodyに任せる

Body（展開部）: 各スライドが独立した1論点に答え、前後のスライドと論旨が積み上がる。S(n) の question は S(n-1) の conclusion がなければ成立しない。

Closing（収束部）: Opening で立てた問いへの「含意」または「次の問い」を1つだけ述べる。前スライドの論点を列挙し直すことを禁止する。
  - 提案書: 次の合意事項・実行条件を1文
  - 説明資料: 全体の論点から示唆される含意を1文
  - DiscussionPaper: 残論点・合意すべき問いを1文
  - 中間報告: 次フェーズの判断ゲート条件を1文

典型構成パターン（デッキ設計の出発点として使う）:
- 観点展開型: S1で観点A/B/Cを提示、S2/S3/S4で各観点を展開、Closingで含意
- 対比展開型: S1で対立軸、S2で現状、S3で代替案、S4で判断軸、Closingで残論点
- 時系列展開型: S1で変化の視点、S2で起点、S3で転機、S4で現在構造、Closingで課題
- 提案展開型: S1で進まない理由、S2で提案定義、S3で初期対象、S4で運用条件、Closingで合意
- 中間報告型: S1で現在地、S2で確認済み事実、S3で未解決論点、S4で検証計画、Closingで判断ゲート

文書種別ごとの構成弱ルール（論証の必然性が優先される場合は順序変更可。省略には明示的な理由が必要）:

提案書（7〜9枚）: 「説得フェーズ」と「実行計画フェーズ」の2層で構成する。
  S1 弊社認識・課題の核心 — 読み手が見落としている問題構造（起点）
  S2 解決策・提案内容の定義 — 何をする/しないの境界（再定義）
  S3 提案骨子・アプローチの根拠 — なぜこの方法か、他の選択肢の棄却（判断根拠）
  S4+ 各論的提案の説明 — 機能・対象・優先度（複数スライド可）
  Sn 他社事例・補強情報 — 現実的に機能するという証拠（省略可: PoC規模）
  Sn+1 スケジュール — いつ何が完了するか
  Sn+2 タスク・役割分担 — 誰が何をするか
  Sn+3 支援体制 — 提案者の関与構造
  Sn+4 見積り — 費用と価値の対比
  Closing 免責・合意要件 — 前提条件 + 今月中の合意事項
  枚数設計: 小提案（試行・PoC）5〜7枚[他社事例・役割分担詳細は省略可]、中提案（フェーズ導入）7〜10枚[全セクション必要]、大提案（全社変革）10〜15枚[各論を複数スライドに展開]

報告書・中間報告（5〜7枚）:
  S1 現在地・状況の核心（起点）
  S2 確認済み事実とエビデンス
  S3 未解決論点と課題の構造
  S4 検証計画・次フェーズの方向
  Closing 判断ゲート条件・今後のアクション

DiscussionPaper（5枚）:
  S1 合意すべき問いの構造（論点地図）
  S2〜S4 論点A・B・C（各論点の独立した展開）
  Closing 残論点・合意条件

説明資料（5枚）:
  S1 この概念が答える問いと分析軸
  S2 定義と境界（何か/何でないか）
  S3 構造の説明
  S4 適用条件と非対象
  Closing 含意・示唆

戦略資料（7枚）:
  S1 変化の起点（なぜ今この判断が必要か）
  S2 現状の限界（現行戦略が機能しない構造的理由）
  S3 方向性の定義と境界
  S4 優先順位と判断軸
  S5 初期対象の選定根拠
  S6 実行条件と体制
  Closing 合意事項と判断集約点

評価・振り返り（5〜7枚）:
  S1 評価の視点と軸（何を基準に振り返るか）
  S2 機能したこと（成功要因の構造）
  S3 機能しなかったこと（失敗・停滞の構造）
  S4 改善の含意（次回への示唆と優先度）
  Closing 合意した変更点（次回のやり方として確定すること）

# Success Criteria
デッキを返す前に以下を満たしていることを確認する:

1. title列挙テスト: 全 title を縦に並べたとき、デッキの論証構造（なぜこの順序でこれらの問いを扱うか）が復元できる。「Aについて、Bについて…」と読める場合は再設計する

2. LM列挙テスト: 全 leading_message を縦に並べたとき、「AがあるからBが問われ、BへのアンサーとしてCが来て、CとDを合わせるとEが出る」という論証の積み上がりが読める。「A・B・C・D・Eという5つの話をした」に読める場合は再設計する

3. 問い独立性: 各スライドの question は他のどのスライドとも異なる固有の問い。page_role だけでなく question の内容で独立を確認する

4. Body必然性: 各 body_content を読み終えた読み手が「LMが正しい」と感じる構造になっている。page_role に応じた構成（判断根拠は代替案棄却・実行計画は条件と完了定義・体制は役割分担など）でLMを支持している

5. Closing非再掲: Closing の leading_message が前スライドの論点を列挙していない

6. handoff連鎖: Closing以外の各スライドの handoff_to_next が「このスライドの結論を受けて次スライドで立つ問い」になっており、次スライドの question と対応している

7. 変化ゴール達成: 全LMを縦に並べて読んだとき、文書種別に対応する変化ゴール（# Goal 参照）が読み手に届く論証になっている

# Constraints
以下は常に守る不変条件:
- 入力にない効果額・改善率・ROI・定量成果は作らない
- body_content: 見出し・箇条書き・Markdownなし。3段落散文
- title: 体言止め名詞句、12〜20字。役割ラベル（「概要」「まとめ」だけのもの）は不可
- leading_message: 普通体の1文（動詞終止形可）。読み手が反論できる具体的な主張であること
- logic_type: 下記13種から選ぶ。causal_chain は使わない
- body_structure.thesis = leading_message と同一の文を設定する
- body_content: 「次のスライドでは」「本資料では」「この章では」といった案内文は不可

# Decision Rules
以下は文脈に応じた判断基準:
- 核心主張が明示されている場合: 全 LM をその核心主張から逆算して設計する（Closingから遡る）
- 問いが2スライドで重複する場合: 1スライドに統合する
- 入力の見出し順が論証順でない場合: 読み手が判断しやすい順序に再編集する
- 同じ概念が再登場する場合: 役割を変えて使う（観点提示 → 詳細説明 → 判断条件 → 実行条件）
- logic_type の選択 — 「出来事→結果→含意」を表したいとき: before_after・issue_split・rationale のいずれかを使う（causal_chain は不可）
- body_content の論理要所:
  - before_after: 転換メカニズムを必ず説明する（「変わった」事実だけでなく「なぜ変わったか」）
  - decision: 採用しなかった選択肢を明示的に棄却する
  - comparison: 比較軸を固定し、各軸での優劣を明示する（特徴の並列だけでは不十分）
  - rationale: 代替案を検討して棄却した上で採用根拠を示す

読み手との関係による Opening/Closing 設計調整（二次分類）:
- 外部向け提案書（競合あり、読み手は懐疑的）: Opening = なぜ今この問題が解けるか、Closing = 最初の合意事項・見積り
- 内部向け提案書（同組織、読み手は協力的だが忙しい）: Opening = なぜ今この投資が必要か、Closing = 承認と次アクション
- 経営向けブリーフィング（時間が極めて短い）: Opening = 今日決めるべきことと判断軸、Closing = 判断の集約点
- RFP回答（要件が先に決まっている）: Opening = 要件理解と解釈の立場表明、Closing = 差別化要因の収束
- キックオフ資料（初回接触、関係者の背景が異なる）: Opening = このプロジェクトがなぜ存在するか、Closing = 全員の初動アクション

提案書の落とし穴（以下のパターンを避ける）:
- 課題→解決策の飛躍: S1で「課題はA」、S2で「解決策はB」だけでは「他にもC・Dがある」と感じさせる。S3で「なぜBがAに対して有効で、C・Dが棄却されるか」を接続する
- 実行計画の附録化: スケジュール・体制・見積りは「この提案が実現可能である証拠」として位置づける。附録になると説得フェーズで論証が終わり読まれなくなる
- 他社事例の装飾化: 「先進事例の紹介」ではなく「うちと類似した条件でBという課題を持つX社が何を達成したか」の形で書く
- 免責だけのClosing: 前提条件の明示に加えて「だからこそ今月中にこれを合意してほしい」を付加する

# Output Format

SlideTitle:
- 体言止め必須。名詞句または「名詞+の+名詞」で終わる
- **主張圧縮の原則**: 中立的なトピック名ではなく、そのスライドの「立場・評価・判断」を表す言葉を含める
  - 問題語: 限界、欠如、空洞、断絶、矛盾、不合理、停滞
  - 根拠語: 合理性、必然性、根拠、要件、前提、条件
  - 転換語: 転換点、変質、再設計の必然
- **文書種別・スライド位置づけによる表現バリエーションを活用すること**:
  提案書の場合:
  - 課題提示スライド: 「（顧客の）XXXX 認識の構造的限界」「弊社が見る XXXX の課題」「XXXX はなぜ機能しないか」
  - 解決策スライド: 「ご提案：XXXX アプローチ」「XXXX の提言」「弊社の XXXX 支援体制」
  - 実行計画スライド: 「Phase 1：XXXX の設計着手」「XXXX ロードマップ」「体制と費用前提」
  DiscussionPaper の場合:
  - 論点地図スライド: 「投資判断の三論点」「XXXX を決める議論の構造」
  - 個別論点スライド: 「論点1：XXXX の判断条件」「論点2：XXXX の責任設計」
  - 合意条件スライド: 「残論点と合意要件」「委員会に問う XXXX の判断」
  戦略資料の場合:
  - 起点スライド: 「背景：XXXX が変わった理由」「XXXX の転換点」
  - 現状分析: 「現行戦略の XXXX 限界」「XXXX が定着しない構造的原因」
  - 方向性: 「優先投資：XXXX への移行」「XXXX が 2026 年度の必然である理由」
- **タイトル末尾の禁止語**: 整理・比較・説明・概要・検討・論点・範囲・境界・構成・一覧・テーマ・ポイント で終わらせない。これらはトピック名であり主張ではない。
  - NG: 「今月確定すべきPoC範囲」「委員会で合意すべき残論点」「設計境界」「導入境界」「XXXX の整理」
  - OK: 「Thin Slice PoC着手の合意要件」「残論点と合意要件」「XXXX の判断条件と責任設計」「XXXX の設計方針と採用根拠」
- **タイトルを縦に並べたとき、デッキの論証が追える**こと。「AについてBについて…」と読める場合は再設計する
- 「全体像」「概要」「まとめ」だけの役割ラベルは不可

LeadingMessage:
- 普通体の1文（動詞終止形可）。40〜90字程度
- 読み手が反論できる具体的な主張（「重要だ」「必要だ」「できない」「〜が根本原因だ」で終わる文が典型）
- Bodyの要約でも予告でもない。Bodyを読まなくてもLMの主張は完結すること
- 「A・B・Cが〜」「A・B・Cは〜」型の個別要素列挙はNG。上位概念で1点の主張にし、個別要素はBodyで展開する
- 入力由来の固有名詞・数値・条件・比較軸・代表例を含め、主張の密度を出す

LM失敗パターン:
- 予告型: 「本ページではAとBとCについて説明する」→ 主張なし
- 複数矢印型: 「AがBになり、CがDになる」→ 矢印が複数で主論点が不明
- Highlight型: 「AはBで、BはCで、CはDである」→ Bodyの要素の列挙
- 空振り型: 「この問題は重要な課題である」→ 当然のことで反論不能

BodyContent:
- 自然な散文。サブタイトル・見出し・箇条書きなし
- logic_type が決める図解骨格（層の名前・比較の軸・ステップの名前）の各要素が本文中で識別できること
- **page_role に応じた構成をとること**:
  - 起点・現状分析: 「なぜ今この問いが重要か」をデータや事実で示し、放置した場合の損失を描く
  - 判断根拠・棄却・比較: 代替案を先に検討し、機能しない理由を示して LM への絞り込みを作る
  - 定義・再定義: 既存概念の限界を示し、提案概念の適用範囲と違いを明示する
  - 実行計画・ロードマップ: 段階・条件・完了定義を具体的に記述し、計画が成立する前提を示す
  - 体制・ガバナンス: 役割分担・責任の所在・例外処理の方針を具体的に書く
  - 合意要件・Closing: 今合意すべき事項と、合意しない場合に発生する具体的な損失を書く
- 全例を羅列しない。読み手の判断に効く代表例を選び、関係性まで書く

body_structure:
- page_role: このページがデッキ全体で担う役割（1〜3語の名詞句。例: 起点、転換点、構造分解、比較、判断、次アクション）
- question: このページが答える問い（1つだけ）
- logic_type: 下記13種から選ぶ
- thesis: leading_message と同一の文
- handoff_to_next: Closing以外は「このスライドの結論を受けて次スライドで立つ問い」（1文）。Closingは空文字

logic_type（13種）:
- comparison: 複数案・複数概念を同じ比較軸で比べ、違いから判断する
- hierarchy: 上位概念 → 下位概念 → 適用先
- process: 入力 → 処理 → 出力 → 検証（実際に順序・入力・出力が主題の場合のみ）
- matrix: 2軸で分類・判断する
- layered_model: 基盤 → 中間層 → 利用層 の積み上げ
- before_after: 現状 → 変化後 → 移行条件（時系列変化・転換点・目的変質はこれを使う）
- decision: 判断対象 → 判断基準 → 推奨/合意 → 実行条件
- issue_split: 大きな論点 → 下位論点 → 判断軸 → 未決事項
- case_analysis: 代表ケースA → 代表ケースB → 共通論点 → 含意
- phased_plan: Phase1 → Phase2 → Phase3 → 判断ゲート（段階導入）
- rationale: 採用理由 → 根拠/原則 → 具体手段 → 含意
- positioning: 既存文脈 → 新要素の役割 → 境界/非対象 → 含意
- operating_policy: 合意方針 → 運用ルール → レビュー条件 → 次アクション

出力例（5スライド提案書。LMの単一主張・論点の独立性・handoff連鎖・Closingの非再掲を確認すること）:
S1（Opening）:
  title: 訪問依存型営業モデルの構造的限界
  logic_type: issue_split
  LM: 「商談数の上限が営業員一人当たりの物理訪問件数に縛られている限り、デジタル時代の法人営業は構造的な成長限界を自力では突破できない」
  handoff_to_next: 「ではこの提案が対象とする案件を正確に定義するとどうなるか」

S2（Body）:
  title: デジタル完結型案件の定義と非対象
  logic_type: positioning
  LM: 「この提案の対象は初期接触から受注まで訪問なしで完結できる案件類型の分離であり、訪問後フォロー手段の追加拡充とは本質的に異なる定義が必要だ」
  handoff_to_next: 「定義された対象の中でどの類型から着手すべきか」

S3（Body）:
  title: デジタル完結型移行の第1優先対象と選定根拠
  logic_type: matrix
  LM: 「現行訪問件数の30%を占める既存顧客の追加購入案件が、初年度デジタル完結型移行の第1優先対象として最も選定根拠が明確だ」
  handoff_to_next: 「選定した対象への移行を担当依存なく確実に機能させる仕組みとは何か」

S4（Body）:
  title: 移行ルールの設計原則と担当依存の排除
  logic_type: operating_policy
  LM: 「移行を担当営業の判断に依存させない唯一の手段は、商品属性・顧客成熟度・案件規模の3軸による自動振り分けルールの設計だ」
  handoff_to_next: 「上記の設計を前提として今月中に何を合意する必要があるか」

S5（Closing）:
  title: 試行開始の合意要件と判断集約点
  logic_type: decision
  LM: 「来月から既存顧客向け追加購入案件30%のデジタル完結処理を第1サイクルとして試行するために、今月中に経営層の合意が必要だ」
  handoff_to_next: ""

# Stop Rules
- title列挙テストまたはLM列挙テストが失敗する場合は修正して返す
- title がトピックラベル（話題を宣言するだけで主張を含まない）になっている場合は修正して返す
- LM がBodyの要素の列挙または予告になっている場合は修正して返す
- body_content がLMを支持する具体的な内容を持たず、page_role に合った構成になっていないスライドがある場合は書き直して返す
- 論証が完成しているなら要求枚数より少なくてよい。枚数を合わせるために論点の薄いスライドを追加しない
"""


@dataclass
class Layer1StructuredGenerator:
    """Layer1 を Pydantic structured output で生成する。"""

    model: str = config.LLM_MODEL or "openai.gpt-5-chat-latest"
    temperature: float = 1.0
    timeout_sec: int = 180
    reasoning_effort: str | None = config.LLM_REASONING_EFFORT
    repair_passes: int = 1

    def invoke(self, user_prompt: str) -> Layer1Deck:
        if ChatOpenAI is None:
            raise ImportError("langchain_openai is required. Run: pip install langchain-openai")
        if not config.LLM_ENDPOINT or not config.LLM_API_KEY:
            raise RuntimeError("LLM endpoint or api key not configured")

        messages = [
            SystemMessage(content=LAYER1_SYSTEM_PROMPT_JA),
            HumanMessage(content=user_prompt.strip()),
        ]

        deck = self._invoke_structured(messages, use_reasoning=True)
        for _ in range(self.repair_passes):
            if not _needs_layer1_repair(deck):
                break
            repair_messages = [
                SystemMessage(content=LAYER1_SYSTEM_PROMPT_JA),
                HumanMessage(
                    content=(
                        "以下のLayer1出力はSuccess Criteriaを一部満たしていません。"
                        "Constraints と Success Criteria を満たすよう修正してください。\n\n"
                        "修正要件:\n"
                        "- title は体言止め（名詞句）にする。述語形（〜した、〜にある）で終わるtitleは修正する\n"
                        "- 各 leading_message は普通体の1文（動詞終止形可）で書く。40〜90字程度。読み手が反論できる具体的な主張であること\n"
                        "- leading_message はこのページの問いへの直接回答1点だけを書く。「A・B・C・Dが〜」型の列挙は禁止\n"
                        "- body_structure.logic_type を必ず設定し、13種から選ぶ。causal_chain は使わない\n"
                        "- body_structure.thesis は leading_message と同一の文を設定する\n"
                        "- body_structure.handoff_to_next はClosing以外の全スライドに設定する。「このスライドの結論を受けて次スライドで立つ問い」を1文で書く\n"
                        "- 各 body_content は page_role に応じた構成でLMを具体的に支持する（判断根拠は代替案棄却・実行計画は段階と条件・体制は役割分担など）\n"
                        "- body_content はサブタイトルや見出しを付けず、1〜3段落の自然な本文で書く\n"
                        "- body_content は leading_message を支える論理的な本文にし、別論点を展開しない\n"
                        "- 入力由来の固有語・数値・比較軸・条件・代表例を、本文として自然に残す\n"
                        "- `根拠1:`、`推奨図解:`、Markdown箇条書きのような内部制作ラベル中心の書き方は避ける\n"
                        "- UserPromptにない効果数値、改善率、ROI、売上増加などを創作しない\n\n"
                        f"UserPrompt:\n{user_prompt.strip()}\n\n"
                        f"CurrentDeckJson:\n{deck.model_dump_json(indent=2)}"
                    )
                ),
            ]
            deck = self._invoke_structured(repair_messages, use_reasoning=True)
        return deck

    def _invoke_structured(self, messages: list, use_reasoning: bool) -> Layer1Deck:
        try:
            return self._build_structured_llm(use_reasoning=use_reasoning).invoke(messages)
        except Exception:
            if use_reasoning and self.reasoning_effort:
                return self._build_structured_llm(use_reasoning=False).invoke(messages)
            raise

    def _build_structured_llm(self, use_reasoning: bool):
        kwargs = {
            "model": self.model,
            "base_url": config.LLM_ENDPOINT,
            "api_key": config.LLM_API_KEY,
            "timeout": self.timeout_sec,
        }
        # Some reasoning models (e.g. gpt-5.5) only support default temperature=1
        if self.temperature != 1.0:
            kwargs["temperature"] = self.temperature
        if use_reasoning and self.reasoning_effort:
            kwargs["model_kwargs"] = {"reasoning_effort": self.reasoning_effort}
        return ChatOpenAI(**kwargs).with_structured_output(Layer1Deck)


def infer_requested_slide_count(user_prompt: str) -> int | None:
    """ユーザー入力から要求枚数を緩く推定する。"""

    text = unicodedata.normalize("NFKC", user_prompt or "")
    patterns = [
        r"([0-9]+|[一二三四五六七八九十]+)\s*ページ",
        r"([0-9]+|[一二三四五六七八九十]+)\s*枚",
        r"全\s*([0-9]+|[一二三四五六七八九十]+)\s*ページ",
        r"([0-9]+|[一二三四五六七八九十]+)\s*slides?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _parse_requested_count_token(match.group(1))
    return None


def _parse_requested_count_token(token: str) -> int:
    normalized = unicodedata.normalize("NFKC", token.strip())
    if normalized.isdigit():
        return int(normalized)

    digits = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if normalized == "十":
        return 10
    if normalized.startswith("十"):
        return 10 + digits.get(normalized[1:], 0)
    if normalized.endswith("十"):
        return digits.get(normalized[:-1], 1) * 10
    if "十" in normalized:
        tens, ones = normalized.split("十", 1)
        return digits.get(tens, 1) * 10 + digits.get(ones, 0)
    if normalized in digits:
        return digits[normalized]
    raise ValueError(f"Unsupported count token: {token}")


def _needs_layer1_repair(deck: Layer1Deck) -> bool:
    for slide in deck.slides:
        body = slide.body_content or ""
        lead = slide.leading_message or ""
        structure = slide.body_structure
        if len(lead) < 25:
            return True
        if not structure.page_role or len(structure.page_role) < 2:
            return True
        if not structure.question or len(structure.question) < 12:
            return True
        if not structure.thesis:
            return True
        if structure.logic_type not in {
            "comparison",
            "hierarchy",
            "process",
            "matrix",
            "layered_model",
            "before_after",
            "decision",
            "issue_split",
            "case_analysis",
            "phased_plan",
            "rationale",
            "positioning",
            "operating_policy",
        }:
            return True
        if re.search(r"根拠[0-9一二三四五六七八九十]*[:：]|推奨図解[:：]", body):
            return True
        if re.search(r"(^|\n)\s*[*\-•#]\s|#{1,6}\s|\*\*", body):
            return True
    return False
