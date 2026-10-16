# gpui-conformance：gpui.rsとgpui.mbtの動作差分を説明できる検証基盤

Status: open — 設計課題。既存ハーネスを拡張するもので、新規実装済み・全面互換とは扱わない。
Priority: P1
Decision date: 2026-10-15
Parent: [ecosystem方針・共通マージ基準](https://github.com/gpui-mbt/gpui.mbt/pull/82)

## 1. 役割

同じシナリオを固定したgpui.rs（Reference Oracle）とgpui.mbt（Candidate）で独立実行し、「どの操作・どの環境・どの観測層で一致／相違したか」を再現可能な証拠として返す。比較対象はGPUIの振る舞いであり、OS全体の認証やアプリ全体の完成判定ではない。

## 2. 現状

[README](../../README.md)には共有fixture、Rust/MoonBit adapter、headless runner、別立てのAppKit/Metal native runner、比較器、固定revision、実行artifactの保持が既にある。portable CIは契約検査であり、両実装やnative実機を毎回起動する証拠ではない。retained imageをvlmkitで診断する経路もあるが、新規native実行や物理入力の確認にはならない。

既存の`pass / mismatch / unsupported / unverified`と終了コードを維持する。概念上のPASS/FAIL等へ表示変換する場合も元の分類を保存し、fixtureや既存結果を無断で改名・上書きしない。

### 既存Linux headless結果（PR #13）

[PR #13](https://github.com/gpui-mbt/gpui-conformance/pull/13) は [merge commit `cdd3cdadf605346ed2b90a59d461697582b8751c`](https://github.com/gpui-mbt/gpui-conformance/commit/cdd3cdadf605346ed2b90a59d461697582b8751c) で取り込まれました。候補gpui.mbt `71da96d9f8eaed89f42937d4edcd3eb2122cfb54` と固定GPUI `d9afb21688e04f89d9e94d96d33eb530aef90886` のLinux比較は **101 pass / 0 mismatch / 1 unsupported / 2 unverified** です。101件はすべてheadless計測で、IMEはunsupported、native window/GPUはunverifiedです。Linux native window/GPUの適合を示すものではありません。

PRの検証記録ではcontract suite 52 tests、original 11-case evidence checker 38 tests、expanded-corpus evidence checker 38 testsがpassしました。生の証拠directory二つとcombined scenario corpusはlocal-onlyであり、[結果ノート](https://github.com/gpui-mbt/gpui-conformance/blob/218b8d387080564970ac696e8862e899f3e14dfc/LINUX_HEADLESS_RESULTS_20261015.md)と記載コマンドだけでは完全な再実行bundleになりません。

[補足コメント](https://github.com/gpui-mbt/gpui-conformance/pull/14#issuecomment-6189651217)を踏まえ、次の作業は既存headless結果の再実装ではなく、証拠bundleの保持・再検証と、native window/GPU・実IMEの別レーンでの検証とする。歴史的な実行報告を削除しない一方、raw artifactを取得できない状態を第三者による再検証済みへ昇格させない。契約検査の件数は両実装の実行ケース数へ足さない。

## 3. 境界と受け渡し

1. gpui.mbtがengine修正を所有し、本repoがfixture・adapter・比較規則・実行証拠を所有する。差分だけが消えるようにoracle側を書き換えない。
2. gpui.rs／依存lock／candidate／suite／toolchainを固定する。upstream Zedはread-onlyで、upstreamへのissue・PR・comment・pushはしない。Rustは開発用参照実装でありgpui.mbt runtimeへ入れない。
3. vlmkitは画像や外部GUI観測の提供者。本repoの互換性判定をVLMの感想やvlmkitのexit 0へ委譲しない。正確なbytes・geometry・event traceを優先する。
4. Yami-kumoはWeb/NativeのUX契約を持つ。本repoがWebの画素とNativeの画素を無条件に一致させたり、gpui.rsにないbrowser実行を捏造したりしない。
5. MZed/dshで見つけたバグはアプリ・アカウント・ネットワークから切り離した最小fixtureとして受け付ける。upstreamとの差が意図的なら、理由・対象・追跡先を残す。

## 4. 実装単位

1. **coverage台帳**：fixture IDごとに観測層、対象API、OS/arch、reference/candidate revision、期待する観測、既知差分、状態、証拠リンクを記録する。既存結果契約への追加はversion付きで行う。
2. **headless回帰**：layout、clip、pointer routing、focusの既存fixtureを土台に、アプリ由来の最小反例と境界条件を追加する。同じ入力を両adapterへ渡し、期待値をそのまま返すstubを認めない。
3. **native profile**：macOS Apple Siliconを優先し、LinuxはWayland/X11など実際のprofile単位で扱う。Windowsは独立profile。window lifecycle、frame、実入力、IME、accessibilityを別々に記録する。未対応OS／観測層は未対応・未検証のまま表示する。
4. **consumerとの連動**：gpui.mbtの候補SHAを明示して実行し、結果を該当PRへ関連付ける。missing case、artifact欠損、古いSHA、未完了processを検査し、過去結果による誤ったGreenを防ぐ。
5. **移送可能な証拠bundle**：既存の二つのraw evidence directoryとcombined corpusを、manifestから解決できる単位として保持する。正確なscenario入力・生成手順、suite/reference/candidate SHA、toolchain/lock、実行コマンド、build/stdout/stderr、観測・readback、比較器が必要とするartifactとhashを揃える。永続保存先・保持条件・取得と検証の手順を記録し、local pathや期限切れartifactだけに依存しない。再配布条件を確認し、認証情報・ユーザーデータを含めない。

## 5. 受入条件

| 対象 | 成立する証拠 | 合格にしてはいけない状態 |
| --- | --- | --- |
| headless比較 | 両実装の実行・非空観測・同一fixture条件・一致する測定値 | JSONだけのgolden、片側未実行 |
| native描画 | 同じ候補の実native frameと取得条件に結び付いた比較 | build-only、headless snapshotだけ |
| 入力／IME／AX | 指定profileで実行した当該操作の観測 | 画面が似ている、内部dispatchだけ |
| negative control | 意図したgeometry／色の差を確実にmismatchへする | 閾値変更で差を隠す |
| 証拠改変・再利用 | 異なるSHA、欠損・改変artifact、空trace、timeoutを拒否する | 未実行をpassへ集計する |
| ユーザー画面の安全 | owned fixtureのみを起動・終了し、許可した観測範囲に限定する | 他windowへ入力、強制activate、任意process kill |
| bundleの移送 | 元のlocal directoryがない別環境で取得・hash検査・既存比較器による再判定ができる | 結果ノートや集計JSONのみ、欠損corpus、期限切れartifact |

明示していない大きな範囲を互換と呼ばない。比較できない環境は`unverified`、仕様上の対象外は理由付き`unsupported`とし、必要なケースが未検証なら受入を保留する。reference実装自体の不具合の可能性も、観測事実と推測を分けて報告する。

bundleを用いた過去証拠の再判定と、固定sourceから両実装を再build・再実行する検証を分ける。再実行には新しいrun IDと新規output directoryを使い、元の証拠を上書きしない。corpus欠損・hash不一致・取得不能をnegative testで拒否する。必要なnative profileやIME実行を準備できない場合も、headless成功は保持しつつ当該レーンを未検証のまま残す。

## 6. 検証方法

既存portable契約検査：`python3 -m unittest discover -s tests -p 'test_portable_contracts.py'`。
両実装比較・native・negative controlはREADMEの実コマンドに、固定sourceと新規output directoryを指定して実行する。実行後にコマンド・対象SHA・profile・PASS/FAIL/未実行と理由を記録する。上記は実装時の検証計画であり、この文書更新で新たなframework実行・bundle検証が完了したとはしない。ローカルとCI内の実行を分け、CI成功の範囲は実際のjob/stepとartifactで示す。

## 7. マージ基準・完了条件

共通`ecosystem-merge-v1`に従う。**最新HEADの必要CIがすべてcompleted/success AND 同じHEADに対する実際の`gpt-6.1-sol/xhigh`レビューがApprove相当**。未解決P0/P1を残さず、モデル・effort・対象SHA・判定・証拠をGitHubに記録する。必要checkのskip、CIなし、古い承認、他モデルへの無断代替は合格にしない。HEAD更新後は再検証・再レビューし、既存の保護を迂回しない。

1. [ ] coverageと観測層・証拠・候補revisionを追跡できる。
2. [ ] アプリ由来の新しい最小fixtureを少なくとも1件、両実装で比較する。
3. [ ] negative controlと欠損／古い証拠の拒否を回帰テストにする。
4. [ ] native・入力・IME等の未検証範囲を隠さず、consumer PRから結果を参照できる。
5. [ ] local-onlyの証拠とcombined corpusを取得可能なbundleにし、別環境での再判定と欠損拒否を確認する。
