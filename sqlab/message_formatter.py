from copy import deepcopy
import json
from .text_tools import TextWrapper, improved_html, improved_text
from html import escape
import re

def create_message_formatter(config: dict) -> callable:

    strings = config["strings"]

    def create_json_formatter() -> callable:
        return lambda data: json.dumps(data, ensure_ascii=False, indent=2)


    def create_html_formatter() -> callable:

        sub_indent = re.compile(r"(?m)^\s+(?=<)").sub
        preamble_accepted = escape(strings["preamble_accepted_without_token"])

        def format_text(text: str) -> str:
            if not text:
                return ""
            text = text.replace("<br>", "")
            text = "\n".join(f"<p>{escape(line.strip())}</p>" for line in text.splitlines())
            return text.replace("<p></p>", "<br>")

        def format_formula(d):
            if "formula" not in d:
                d["formula"] = ""
                return
            tweak = d['formula'].get("tweak", "")
            code = d["formula"].get("code", "")
            d["formula"] = f'''
                <div class="formula">
                    <div class="tweak">{escape(tweak)}</div>
                    <div class="code">{escape(code)}</div>
                </div>
            '''
        
        def format_solutions(d):
            if "solutions" not in d:
                d["solutions"] = ""
                return
            acc = ['<div class="solutions">']
            for x in d["solutions"]:
                if "solution" in x:
                    acc.append('<div class="solution">')
                    if preamble := x["solution"].get("preamble"):
                        acc.append(f'<div class="intro">{format_text(preamble)}</div>')
                    acc.append(f'<pre class="query">{escape(x["solution"]["query"])}</pre>')
                    acc.append('</div>')
                elif "annotation" in x:
                    acc.append(f'<div class="annotation">{format_text(x["annotation"])}</div>')
            acc.append('</div>')
            d["solutions"] = "\n".join(acc)

        def data_to_html(data):
            if "hint" in data:
                d = deepcopy(data["hint"])
                html = f'''
                    <div class="hint">
                        <div class="label">{escape(d["label"])}</div>
                        <div class="counter">{d["counter"]}</div>
                        <div class="preamble">{escape(d["preamble"])}</div>
                        <div class="text">
                            {format_text(d["text"])}
                        </div>
                    </div>
                '''
            elif "exercise_statement" in data:
                d = deepcopy(data["exercise_statement"])
                format_formula(d)
                html = f'''
                    <div class="exercise-statement">
                        <div class="label">{escape(d["label"])}</div>
                        <div class="counter">{d["counter"]}</div>
                        <div class="text">
                            {format_text(d["statement"])}
                        </div>
                        {d["formula"]}
                    </div>
                '''
            elif "exercise_correction" in data:
                d = deepcopy(data["exercise_correction"])
                format_solutions(d)
                html = f'''
                    <div class="exercise-correction">
                        <div class="label">{escape(d["label"])}</div>
                        <div class="counter">{d["counter"]}</div>
                        <div class="preamble">{preamble_accepted}</div>
                        {d["solutions"]}
                    </div>
                '''
            elif "episode" in data:
                d = deepcopy(data["episode"])
                format_solutions(d)
                format_formula(d)
                html = f'''
                    <div class="episode-statement">
                        <div class="label">{escape(d["label"])}</div>
                        <div class="counter">{d["counter"]}</div>
                        <div class="text">
                            {format_text(d["context"])}
                        </div>
                        <div class="statement">
                            <div class="label">{escape(d["statement_label"])}</div>
                            <div class="text">
                                {format_text(d["statement"])}
                            </div>
                        </div>
                        {d["formula"]}
                    </div>
                    <div class="episode-correction">
                        <div class="label">{escape(d["label"])}</div>
                        <div class="counter">{d["counter"]}</div>
                        <div class="preamble">{preamble_accepted}</div>
                        {d["solutions"]}
                    </div>
                '''
            html = improved_html(html)
            html = sub_indent("", html)
            return html

        return data_to_html


    def create_text_formatter() -> callable:

        preamble_accepted = strings["preamble_accepted"]
        
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
                    if preamble := x["solution"].get("preamble"):
                        acc.append(preamble)
                    acc.append(x["solution"]["query"])
                else:
                    acc.append(x["annotation"])
            acc.append(hr)
            d["solutions"] = "\n\n".join(acc)

        def data_to_text(data):
            if "hint" in data:
                d = deepcopy(data["hint"])
                template = "🟠 **{label} {counter}**. {preamble}\n\n➥ {text}"
            elif "exercise_statement" in data:
                d = deepcopy(data["exercise_statement"])
                format_formula(d)
                template = "⚪️ **{label} {counter}**. {statement}\n\n{formula}\n"
            elif "exercise_correction" in data:
                d = deepcopy(data["exercise_correction"])
                format_solutions(d)
                d["preamble"] = preamble_accepted.format(token=d["token"])
                template = "🟢 **{label} {counter}**. {preamble}{solutions}\n"
            elif "episode" in data:
                d = deepcopy(data["episode"])
                format_solutions(d)
                format_formula(d)
                d["emoji"] = "🟢" if d["counter"] > 1 else "⚪️"
                d["preamble"] = preamble_accepted.format(token=d["token"])
                template = "{emoji} **{label} {counter}**. {preamble}{solutions}\n\n{context}\n\n**{statement_label}**. {statement}\n\n{formula}\n"
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
