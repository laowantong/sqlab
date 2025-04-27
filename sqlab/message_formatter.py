from copy import deepcopy
import json
from .text_tools import TextWrapper, improved_html, improved_text

def create_message_formatter(config: dict) -> callable:

    def create_json_formatter() -> callable:
        return lambda data: json.dumps(data, ensure_ascii=False, indent=2)


    def create_html_formatter() -> callable:

        def data_to_html(data, level=0):
            indent = '  ' * level
            if isinstance(data, dict):
                return '\n'.join(
                    f'{indent}<div class="{key}">\n{data_to_html(value, level + 1)}\n{indent}</div>'
                    for key, value in data.items()
                )
            elif isinstance(data, list):
                return '\n'.join(data_to_html(item, level) for item in data)
            elif isinstance(data, str):
                return improved_html(data)
            else:
                return str(data)
        
        return data_to_html


    def create_text_formatter() -> callable:
        
        def format_formula(d):
            if "formula" not in d:
                d["formula"] = ""
                return
            if d["formula"]["tweak"]:
                d["formula"]["tweak"] = f" ({d['formula']['tweak']})"
            d["formula"] = "**{label}**{tweak}.\n-- , {code}".format_map(d["formula"])
        
        def format_solutions(d):
            if "solutions" not in d:
                d["solutions"] = ""
                return
            acc = [""]
            acc.append(hr)
            for x in d["solutions"]:
                if "solution" in x:
                    if x["solution"]["preamble"]:
                        acc.append(x["solution"]["preamble"])
                    acc.append(x["solution"]["query"])
                else:
                    acc.append(x["annotation"])
            acc.append(hr)
            d["solutions"] = "\n\n".join(acc)

        def data_to_text(data):
            if "hint" in data:
                d = deepcopy(data["hint"])
                template = "🟠 {counter}. {preamble}\n\n➥ {text}"
            elif "exercise_statement" in data:
                d = deepcopy(data["exercise_statement"])
                format_formula(d)
                template = "⚪️ **{label} {counter}**. {statement}\n\n{formula}\n"
            elif "exercise_correction" in data:
                d = deepcopy(data["exercise_correction"])
                format_solutions(d)
                template = "🟢 {counter}. {preamble}{solutions}\n"
            elif "episode" in data:
                d = deepcopy(data["episode"])
                format_solutions(d)
                format_formula(d)
                d["emoji"] = "🟢" if d["counter"] > 1 else "⚪️"
                template = "{emoji} {counter}. {preamble}{solutions}\n\n{context}\n\n**{statement_label}**. {statement}\n\n{formula}\n"
            text = template.format_map(d)
            text = improved_text(text)
            text = wrap_text(text)
            return text

        wrap_text = TextWrapper(config)
        column_width = config.get("column_width") or 100
        hr = "-" * column_width
        return data_to_text

    output_format = config["markdown_to"]
    if output_format == "json":
        return create_json_formatter()
    elif output_format == "html":
        return create_html_formatter()
    elif output_format == "text":
        return create_text_formatter()
    else:
        raise ValueError(f"Unknown output format: {output_format}")
