from copy import deepcopy
import json
from .text_tools import TextWrapper, markdown_to_html, improved_text
from html import escape
import re
from textwrap import dedent

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
        preamble_accepted = escape(strings["preamble_accepted"])

        def format_text(text: str) -> str:
            """
            Format running text:
            - Suppress existing <br> tags.
            - Add <p> tags to each line, except for code blocks.
            - Escape HTML special characters.
            """
            text = sub_mark("", text) # Remove all token-related explanations
            text = dedent(text)
            return markdown_to_html(text)

        def format_solutions(data):
            if data.get("solutions"):
                acc = ["<div class='solutions'>"]
                for x in data["solutions"]:
                    if "solution" in x:
                        acc.append("<div class='solution'>")
                        if intro := x["solution"].get("intro"):
                            acc.append(f"<div class='intro'>{format_text(intro)}</div>")
                        acc.append(format_text(f"```sql\n{x['solution']['query']}\n```"))
                        acc.append("</div>")
                    elif "annotation" in x:
                        acc.append(f"<div class='annotation'>{format_text(x['annotation'])}</div>")
                acc.append("</div>")
                data["solutions"] = "\n".join(acc)

        def to_web(kind, data):
            data = deepcopy(data)
            format_solutions(data)
            task_data = {}
            if kind == "hint":
                task_data["category"] = "specific-hint"
                task_data["feedback"] = f"""
                    <div class='preamble'>{escape(data['preamble'])}</div>
                    <div class='text'>
                        {format_text(data['text'])}
                    </div>
                """
            elif kind == "exercise_task":
                task_data["description"] = f"""
                    <div class='exercise description'>
                        <div class='label'>{escape(data['label'])}</div>
                        <div class='number'>{data['task_number']}</div>
                        <div class='text'>{format_text(data['statement'])}</div>
                    </div>
                """
            elif kind == "exercise_correction":
                task_data["category"] = "correction"
                task_data["feedback"] = f"""
                    <div class='preamble'>{preamble_accepted}</div>
                    {data['solutions']}
                """
            else:
                assert kind == "episode", f"Unknown kind: {kind}"
                if data["task_number"] > 1:
                    task_data["category"] = "correction"
                    task_data["feedback"] = f"""
                        <div class='preamble'>{preamble_accepted}</div>
                        {data['solutions']}
                    """
                if data["statement"]:
                    context = format_text(data['context'])
                    # Add a lettrine iff the first character is a letter
                    context = re.sub(r"^(<p>)(\w)", r"\1<span class='lettrine'>\2</span>", context)
                    task_data["description"] = f"""
                        <div class='episode description'>
                            <div class='label'>{escape(data['label'])}</div>
                            <div class='number'>{data['task_number']}</div>
                            <div class='context'>{context}</div>
                            <div class='statement'>
                                <div class='label'>{escape(data['statement_label'])}</div>
                                <div class='text'>{format_text(data['statement'])}</div>
                            </div>
                        </div>
                    """
                else: # Episode without statement = last episode
                    task_data["description"] = f"""
                        <div class='episode description'>
                            <div class='context'>
                                {format_text(data['context'])}
                            </div>
                        </div>
                    """
            for (k, v) in task_data.items():
                task_data[k] = sub_indent("", v)
            return json.dumps(task_data, ensure_ascii=False, indent=2)

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
