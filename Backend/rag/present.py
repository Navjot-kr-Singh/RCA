"""Formats an /analyze response as short chat Markdown (Discord, Slack)."""

NOVEL_NOTE = "No similar past incident was found; these hypotheses are model reasoning only."


def _pct(x):
    return f"{round(float(x) * 100)}%"


def summary_markdown(result):
    a = result["analysis"]
    rag = result["mode"] == "RAG"
    lines = [f"**RCA ({result['mode']})** · category `{a['category']}` · severity **{a['severity']}**"]
    if not rag:
        lines.append(f"_{NOVEL_NOTE}_")
    lines.append(a["summary"])

    lines += ["", "**Hypotheses**"]
    for n, h in enumerate(a["hypotheses"], 1):
        evidence = ", ".join(h["evidence_ids"]) or "no past incident"
        lines.append(f"{n}. {h['cause']} ({_pct(h['likelihood'])}, evidence: {evidence})")

    if rag and result["similar_incidents"]:
        s = result["similar_incidents"][0]
        url = f" <{s['source_url']}>" if s.get("source_url") else ""
        lines += ["", f"**Closest past incident:** {s['id']} ({s['org']}){url}"]

    lines += ["", "**First checks**"]
    lines += [f"{n}. {c}" for n, c in enumerate(a["first_checks"], 1)]

    demo = result.get("demo")
    if demo:
        lines += ["", f"_Demo mode: cached answer for \"{demo['matched_issue']}\"._"]
    return "\n".join(lines)
