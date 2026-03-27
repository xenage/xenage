import CodeMirror from "@uiw/react-codemirror";
import { yaml } from "@codemirror/lang-yaml";
import { oneDark } from "@codemirror/theme-one-dark";

type YamlCodeEditorProps = {
  onChange: (value: string) => void;
  value: string;
};

export function YamlCodeEditor({ onChange, value }: YamlCodeEditorProps) {
  return (
    <CodeMirror
      basicSetup={{
        autocompletion: true,
        foldGutter: true,
        highlightActiveLine: true,
        lineNumbers: true,
      }}
      className="yaml-code-editor"
      extensions={[yaml()]}
      height="100%"
      onChange={onChange}
      theme={oneDark}
      value={value}
    />
  );
}
