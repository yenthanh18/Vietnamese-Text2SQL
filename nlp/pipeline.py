import re
import torch

#Final NLP pipeline exported from the evaluation notebook.
#Runtime objects such as model, tokenizer, schema and DEW dictionary
#are initialized by the web backend.



def build_schema_text(db_id, tables_data):
    schema = next(
        item for item in tables_data
        if item["db_id"] == db_id
    )

    lines = []

    for table_id, table_name in enumerate(schema["table_names"]):
        columns = [
            column_name
            for column_table_id, column_name in schema["column_names"]
            if column_table_id == table_id
        ]

        lines.append(
            f"Table {table_id}: {table_name} | "
            f"Columns: {', '.join(columns)}"
        )

    return "\n".join(lines)


def run_dew(question, db_id, dew_dict, max_ngram=8):
    tokens = question.lower().split()
    candidates = []
    db_dict = dew_dict[db_id]

    for n in range(min(max_ngram, len(tokens)), 0, -1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i+n])
            entries = db_dict["entries"].get(phrase, [])

            for entry in entries:
                candidates.append({
                    "text": phrase,
                    "start": i,
                    "end": i + n,
                    "entity_type": entry["entity_type"],
                    "table_id": entry["table_id"],
                    "column_id": entry["column_id"],
                    "name": entry["name"]
                })

    candidates.sort(
        key=lambda x: (
            -(x["end"] - x["start"]),
            x["start"]
        )
    )

    selected_spans = []
    selected = []

    for match in candidates:
        span = (match["start"], match["end"])

        if span in selected_spans:
            selected.append(match)
            continue

        overlap = any(
            not (match["end"] <= start or match["start"] >= end)
            for start, end in selected_spans
        )

        if not overlap:
            selected_spans.append(span)
            selected.append(match)

    selected.sort(
        key=lambda x: (
            x["start"],
            x["end"],
            x["entity_type"],
            x["table_id"],
            x["column_id"] if x["column_id"] is not None else -1
        )
    )

    return selected


def apply_dew_tags(question, db_id, dew_dict):
    matches = run_dew(question, db_id, dew_dict)

    tokens = question.split()
    normalized_tokens = question.lower().split()
    span_tags = {}

    for match in matches:
        span = (match["start"], match["end"])

        if span not in span_tags:
            original_text = " ".join(tokens[match["start"]:match["end"]])

            span_tags[span] = {
                "text": original_text,
                "entity_type": match["entity_type"],
                "candidates": []
            }

        span_tags[span]["candidates"].append({
            "table_id": match["table_id"],
            "column_id": match["column_id"]
        })

    tagged_tokens = tokens.copy()

    for (start, end), info in sorted(
        span_tags.items(),
        reverse=True
    ):
        tag = "TABLE" if info["entity_type"] == "table" else "COL"
        replacement = f"[{tag}: {info['text']}]"
        tagged_tokens[start:end] = [replacement]

    return " ".join(tagged_tokens), span_tags


def build_table_column_map(db_id):
    schema = vt_map[db_id]

    table_column_map = {}

    for table_id, table_name in enumerate(
        schema["table_names"]
    ):
        columns = [
            column_name.lower()
            for column_table_id, column_name
            in schema["column_names"]
            if column_table_id == table_id
        ]

        table_column_map[
            table_name.lower()
        ] = columns

    return table_column_map


def extract_alias_context(sql_text, db_id):
    table_column_map = build_table_column_map(db_id)

    alias_map = {}

    pattern = re.compile(
        r"\b(?:from|join)\s+(.+?)"
        r"(?:\s+(?:as\s+)?([A-Za-z_]\w*))"
        r"(?=\s+(?:join|on|where|group|order|having|limit|$))",
        flags=re.IGNORECASE
    )

    for match in pattern.finditer(sql_text):
        table_name = match.group(1).strip().lower()
        alias = match.group(2).lower()

        if table_name in table_column_map:
            alias_map[alias] = {
                "table": table_name,
                "columns": table_column_map[table_name]
            }

    return alias_map


def count_schema_violations(sql, db_id):
    alias_context = extract_alias_context(sql.lower(), db_id)
    schema = vt_map[db_id]
    all_columns = sorted({c.lower() for t, c in schema["column_names"] if t >= 0}, key=len, reverse=True)
    violations = 0

    for alias, info in alias_context.items():
        valid_columns = set(info["columns"])
        for match in re.finditer(rf"(?<!\w){re.escape(alias)}\.", sql.lower()):
            remaining = sql.lower()[match.end():]
            matched = next((c for c in all_columns if remaining.startswith(c) and (len(remaining) == len(c) or not remaining[len(c)].isalnum())), None)
            if matched is not None and matched not in valid_columns:
                violations += 1

    return violations


def generate_e2_sql(sample):
    schema_text = build_schema_text(
        sample["db_id"],
        tables_data
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": (
                f"Database schema:\n{schema_text}\n\n"
                f"Question:\n{sample['question']}"
            )
        }
    ]

    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True
    )

    inputs = {
        key: value.to(model_e2.device)
        for key, value in inputs.items()
    }

    with torch.inference_mode():
        outputs = model_e2.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    prompt_length = inputs["input_ids"].shape[-1]
    generated_ids = outputs[0][prompt_length:]

    sql = tokenizer.decode(
        generated_ids,
        skip_special_tokens=True
    ).strip()

    return sql


def generate_e3_candidates(sample, num_beams=5, num_return_sequences=5):
    schema_text = build_schema_text(sample["db_id"], tables_data)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Database schema:\n{schema_text}\n\nQuestion:\n{sample['question']}"}
    ]

    inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True)
    inputs = {k: v.to(model_e2.device) for k, v in inputs.items()}
    prompt_length = inputs["input_ids"].shape[-1]

    with torch.inference_mode():
        outputs = model_e2.generate(
            **inputs, max_new_tokens=256, do_sample=False,
            num_beams=num_beams, num_return_sequences=num_return_sequences,
            return_dict_in_generate=True, output_scores=True,
            early_stopping=True, pad_token_id=tokenizer.eos_token_id
        )

    candidates = []
    for output, score in zip(outputs.sequences, outputs.sequences_scores):
        sql = tokenizer.decode(output[prompt_length:], skip_special_tokens=True).strip()
        if sql not in [x["sql"] for x in candidates]:
            candidates.append({"sql": sql, "model_score": float(score)})

    return candidates


def select_e3_candidate(candidates, db_id):
    scored = []
    for item in candidates:
        violations = count_schema_violations(item["sql"], db_id)
        scored.append({**item, "violations": violations})

    valid = [x for x in scored if x["violations"] == 0]
    pool = valid if valid else scored
    return max(pool, key=lambda x: x["model_score"])
