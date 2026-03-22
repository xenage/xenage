import { YamlCodeEditor } from "./YamlCodeEditor";

type RbacEditorTabContentProps = {
  applying: boolean;
  onApply: () => void;
  onYamlChange: (value: string) => void;
  status: string | null;
  yaml: string;
};

export function RbacEditorTabContent({
  applying,
  onApply,
  onYamlChange,
  status,
  yaml,
}: RbacEditorTabContentProps) {
  return (
    <div className="rbac-editor-content">
      <div className="rbac-editor-content__toolbar">
        <button className="rbac-editor-apply" disabled={applying} onClick={onApply} type="button">Apply</button>
      </div>
      <div className="rbac-editor-content__editor">
        <YamlCodeEditor onChange={onYamlChange} value={yaml} />
      </div>
      {status ? <div className="event-layout__pager">{status}</div> : null}
    </div>
  );
}
