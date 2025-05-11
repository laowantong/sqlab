from copy import deepcopy
import json
from .text_tools import TextWrapper, improved_html, improved_text
from html import escape
import re

def create_message_formatter(config: dict) -> callable:

    strings = config["strings"]
    sub_mark = re.compile(r"(?s)<mark>(.*?)</mark>").sub

    def create_json_formatter() -> callable:
        return lambda x: json.dumps(
                {
                    "kind": x[0],
                    "data": x[1],
                },
                ensure_ascii=False,
                indent=2
        )


    def create_web_formatter() -> callable:

        sub_indent = re.compile(r"(?m)^\s+(?=<)").sub
        preamble_accepted = escape(strings["preamble_accepted_without_token"])

        def format_text(text: str) -> str:
            """
            Format running text:
            - Suppress existing <br> tags.
            - Add <p> tags to each line, except for code blocks.
            - Escape HTML special characters.
            - Add <br> tags for empty lines.
            """
            text = sub_mark("", text) # Remove all token-related explanations
            text = text.replace("<br>", "")
            acc = []
            needs_p = True
            for line in text.splitlines():
                if line.startswith("```"):
                    needs_p = not needs_p
                if needs_p and not line.startswith("```"):
                    if line.strip():
                        acc.append(f"<p>{escape(line.strip())}</p>")
                    else:
                        acc.append("<br>")
                else:
                    acc.append(escape(line))
            return "\n".join(acc)

        def format_solutions(data):
            if data.get("solutions"):
                acc = ["<div class='solutions'>"]
                for x in data["solutions"]:
                    if "solution" in x:
                        acc.append("<div class='solution'>")
                        if intro := x["solution"].get("intro"):
                            acc.append(f"<div class='intro'>{format_text(intro)}</div>")
                        acc.append(f"<pre><code class='sql'>{escape(x['solution']['query'])}</code></pre>")
                        acc.append("</div>")
                    elif "annotation" in x:
                        acc.append(f"<div class='annotation'>{format_text(x['annotation'])}</div>")
                acc.append("</div>")
                data["solutions"] = "\n".join(acc)

        def to_web(kind, data):
            data = deepcopy(data)
            format_solutions(data)
            web = {}
            if kind == "hint":
                web["feedback"] = f"""
                    <div class='hint'>
                        <div class='label'>{escape(data['label'])}</div>
                        <div class='number'>{data['task_number']}</div>
                        <div class='preamble'>{escape(data['preamble'])}</div>
                        <div class='text'>
                            {format_text(data['text'])}
                        </div>
                    </div>
                """
            elif kind == "exercise_task":
                web["task"] = f"""
                    <div class='exercise task'>
                        <div class='label'>{escape(data['label'])}</div>
                        <div class='number'>{data['task_number']}</div>
                        <div class='text'>{format_text(data['statement'])}</div>
                    </div>
                """
            elif kind == "exercise_correction":
                web["feedback"] = f"""
                    <div class='correction'>
                        <div class='label'>{escape(data['label'])}</div>
                        <div class='number'>{data['task_number']}</div>
                        <div class='preamble'>{preamble_accepted}</div>
                        {data['solutions']}
                    </div>
                """
            else:
                assert kind == "episode", f"Unknown kind: {kind}"
                if data["task_number"] > 1:
                    web["feedback"] = f"""
                        <div class='correction'>
                            <div class='label'>{escape(data['label'])}</div>
                            <div class='number'>{data['task_number'] - 1}</div>
                            <div class='preamble'>{preamble_accepted}</div>
                            {data['solutions']}
                        </div>
                    """
                if data["statement"]:
                    web["task"] = f"""
                        <div class='episode task'>
                            <div class='label'>{escape(data['label'])}</div>
                            <div class='number'>{data['task_number']}</div>
                            <div class='context'>{format_text(data['context'])}</div>
                            <div class='statement'>
                                <div class='label'>{escape(data['statement_label'])}</div>
                                <div class='text'>{format_text(data['statement'])}</div>
                            </div>
                        </div>
                    """
                else: # Episode without statement = last episode
                    web["task"] = f"""
                        <div class='episode task'>
                            <div class='context'>
                                {format_text(data['context'])}
                            </div>
                        </div>
                    """
            for (k, v) in web.items():
                web[k] = sub_indent("", improved_html(v))
            if "formula" in data:
                d = {}
                d["code"] = data["formula"]["code"]
                if data["formula"]["tweak"]:
                    d["tweak"] = data["formula"].get("tweak_javascript", "TODO")
                web["formula"] = d
            return json.dumps(web, ensure_ascii=False, indent=2)

        return lambda couple: to_web(*couple)


    def create_txt_formatter() -> callable:

        preamble_accepted = strings["preamble_accepted"]
        
        def format_formula(data):
            if data.get("formula"):
                if data["formula"]["tweak"]:
                    data["formula"]["tweak"] = f" ({data['formula']['tweak']})"
                data["formula"] = "**{label}**{tweak}.\n-- , {code}".format_map(data["formula"])
        
        def format_solutions(data):
            if data.get("solutions"):
                acc = [hr]
                for x in data["solutions"]:
                    if "solution" in x:
                        if intro := x["solution"].get("intro"):
                            acc.append(intro)
                        acc.append(x["solution"]["query"])
                    else:
                        acc.append(x["annotation"])
                acc.append(hr)
                data["solutions"] = "\n\n".join(acc)

        def to_txt(kind, data):
            data = deepcopy(data)
            format_formula(data)
            format_solutions(data)
            if data.get("solutions"):
                data["preamble"] = preamble_accepted.format(token=data.get("token"))
            if kind == "hint":
                template = "🟠 **{label} {task_number}**. {preamble}\n\n➥ {text}"
            elif kind == "exercise_task":
                template = "⚪️ **{label} {task_number}**. {statement}\n\n{formula}\n"
            elif kind == "exercise_correction":
                template = "🟢 **{label} {task_number}**. {preamble}\n\n{solutions}\n"
            else:
                assert kind == "episode", f"Unknown kind: {kind}"
                if data["task_number"] == 1: # first episode
                    template = "⚪️ **{label} {task_number}**.\n\n{context}\n\n**{statement_label}**. {statement}\n\n{formula}\n"
                elif data.get("formula"): # subsequent episode with statement
                    template = "🟢 **{label} {task_number}**. {preamble}\n\n{solutions}\n\n{context}\n\n**{statement_label}**. {statement}\n\n{formula}\n"
                else: # last episode
                    template = "🟢 **{label} {task_number}**. {preamble}\n\n{solutions}\n\n{context}\n\n"
            result = template.format_map(data)
            result = improved_text(result)
            result = wrap_text(result)
            return result

        wrap_text = TextWrapper(config)
        column_width = config.get("column_width") or 100
        hr = "-" * column_width
        return lambda couple: to_txt(*couple)

    output_format = config["markdown_to"]
    if output_format == "json":
        return create_json_formatter()
    elif output_format == "web":
        return create_web_formatter()
    elif output_format == "txt":
        return create_txt_formatter()
    else:
        raise ValueError(f"Unknown output format: {output_format}")
