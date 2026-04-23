# Section Taxonomy

Canonical sections for Taiwan criminal judgments. The segmenter normalizes every heading below to the canonical label on the left.

| Canonical label | Regex (on normalized line) | Aliases / notes |
|-----------------|----------------------------|-----------------|
| `主文` | `^\s*主\s*文\s*$` | Operative holding; always appears near the top. |
| `事實及理由` | `^\s*事\s*實(\s*及\s*理\s*由)?\s*$` | Merged section used in simplified (簡易) judgments. |
| `犯罪事實` | `^\s*犯\s*罪\s*事\s*實\s*$` | Standalone in complex judgments or in the prosecutor's 聲請簡易判決處刑書 appendix. |
| `證據及所犯法條` | `^\s*證\s*據(\s*及\s*所\s*犯\s*法\s*條)?\s*$` | Sometimes just `證據`. |
| `理由` | `^\s*理\s*由\s*$` | Reasoning-only section (not `事實及理由`). |
| `論罪科刑` | `^\s*論\s*罪\s*科\s*刑\s*$` | Present in full judgments. |
| `據上論斷` | `^\s*據\s*上\s*論\s*斷.*$` | Usually followed by the statutes cited. |
| `附錄法條` | `^\s*附\s*錄.*法\s*條.*$` | Statute appendix. |
| `未分段` | _fallback_ | Whole document when no anchors match. |

## Design notes

- Anchors live on their own line after page-marker stripping. We deliberately require a dedicated heading line to avoid false positives inside running prose (e.g. the word `主文` appearing inside a sentence).
- Aliases use the same canonical label - downstream extractors only need to switch on `label`.
- The 聲請簡易判決處刑書 appendix can contain a second `犯罪事實` and `證據及所犯法條`. The segmenter keeps them as separate sections in document order (sec-NN increments).
- Paragraph splitting: blank lines first, then Chinese ordinal bullets (`一、二、三、...十、`) inside a section. Sub-bullets (`(一)`, `1.`) are kept inside their parent paragraph.

## Paragraph ID scheme

- Format: `p-NNN`, zero-padded to 3 digits, globally unique across the document.
- Allocated in a single forward pass; deterministic for a given input.
- Section IDs use `sec-NN` (2 digits) to keep them visually distinct from paragraph IDs in audit trails.
