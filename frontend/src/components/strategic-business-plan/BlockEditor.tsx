import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Plus, X } from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

type TextBlock = {
  id: string;
  type: 'h1' | 'h2' | 'h3' | 'h4' | 'p' | 'blockquote';
  text: string;
  attrs: string;
};

type ListBlock = {
  id: string;
  type: 'ul' | 'ol';
  items: { id: string; text: string; attrs: string }[];
  attrs: string;
};

type TableCell = { id: string; text: string; isHeader: boolean; attrs: string };
type TableRow = { id: string; cells: TableCell[]; attrs: string };
type TableBlock = {
  id: string;
  type: 'table';
  rows: TableRow[];
  attrs: string;
};

type Block = TextBlock | ListBlock | TableBlock;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getAttrs(el: Element): string {
  return Array.from(el.attributes)
    .map((a) => `${a.name}="${a.value}"`)
    .join(' ');
}

function openTag(tag: string, attrs: string): string {
  return attrs ? `<${tag} ${attrs}>` : `<${tag}>`;
}

// ─── Parser ───────────────────────────────────────────────────────────────────

function parseTableElement(el: Element): TableBlock {
  const rows: TableRow[] = [];

  Array.from(el.querySelectorAll('tr')).forEach((tr) => {
    const cells: TableCell[] = [];
    tr.querySelectorAll('th, td').forEach((cell) => {
      cells.push({
        id: crypto.randomUUID(),
        text: cell.textContent?.trim() || '',
        isHeader: cell.tagName.toLowerCase() === 'th',
        attrs: getAttrs(cell),
      });
    });
    if (cells.length > 0) {
      rows.push({ id: crypto.randomUUID(), cells, attrs: getAttrs(tr) });
    }
  });

  return { id: crypto.randomUUID(), type: 'table', rows, attrs: getAttrs(el) };
}

function htmlToBlocks(html: string): Block[] {
  const doc = new DOMParser().parseFromString(`<div id="root">${html}</div>`, 'text/html');
  const root = doc.getElementById('root');
  if (!root) return [];

  const blocks: Block[] = [];

  root.childNodes.forEach((node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent?.trim();
      if (text) {
        blocks.push({ id: crypto.randomUUID(), type: 'p', text, attrs: '' });
      }
      return;
    }

    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const el = node as Element;
    const tag = el.tagName.toLowerCase();

    if (['h1', 'h2', 'h3', 'h4'].includes(tag)) {
      blocks.push({ id: crypto.randomUUID(), type: tag as TextBlock['type'], text: el.textContent || '', attrs: getAttrs(el) });
      return;
    }

    if (tag === 'p' || tag === 'blockquote') {
      blocks.push({ id: crypto.randomUUID(), type: tag as TextBlock['type'], text: el.textContent || '', attrs: getAttrs(el) });
      return;
    }

    if (tag === 'ul' || tag === 'ol') {
      const items = Array.from(el.querySelectorAll(':scope > li')).map((li) => ({
        id: crypto.randomUUID(),
        text: li.textContent || '',
        attrs: getAttrs(li),
      }));
      if (items.length > 0) {
        blocks.push({ id: crypto.randomUUID(), type: tag as ListBlock['type'], items, attrs: getAttrs(el) });
      }
      return;
    }

    if (tag === 'table') {
      blocks.push(parseTableElement(el));
      return;
    }

    // Unknown tag — extract plain text, wrap as paragraph
    const text = el.textContent?.trim();
    if (text) {
      blocks.push({ id: crypto.randomUUID(), type: 'p', text, attrs: '' });
    }
  });

  return blocks;
}

// ─── Serializer ───────────────────────────────────────────────────────────────

function serializeTable(block: TableBlock): string {
  const hasHeader = block.rows[0]?.cells.some((c) => c.isHeader);

  if (hasHeader) {
    const headerRow = block.rows[0];
    const bodyRows = block.rows.slice(1);
    const thead = `<thead>${openTag('tr', headerRow.attrs)}${headerRow.cells.map((c) => `${openTag('th', c.attrs)}${c.text}</th>`).join('')}</tr></thead>`;
    const tbody =
      bodyRows.length > 0
        ? `<tbody>${bodyRows.map((r) => `${openTag('tr', r.attrs)}${r.cells.map((c) => `${openTag('td', c.attrs)}${c.text}</td>`).join('')}</tr>`).join('')}</tbody>`
        : '';
    return `${openTag('table', block.attrs)}${thead}${tbody}</table>`;
  }

  const tbody = `<tbody>${block.rows.map((r) => `${openTag('tr', r.attrs)}${r.cells.map((c) => `${openTag('td', c.attrs)}${c.text}</td>`).join('')}</tr>`).join('')}</tbody>`;
  return `${openTag('table', block.attrs)}${tbody}</table>`;
}

function blocksToHtml(blocks: Block[]): string {
  return blocks
    .map((block) => {
      if (block.type === 'table') return serializeTable(block);
      if (block.type === 'ul' || block.type === 'ol') {
        const items = block.items.map((item) => `${openTag('li', item.attrs)}${item.text}</li>`).join('');
        return `${openTag(block.type, block.attrs)}${items}</${block.type}>`;
      }
      return `${openTag(block.type, block.attrs)}${block?.text}</${block.type}>`;
    })
    .join('\n');
}

// ─── Component ────────────────────────────────────────────────────────────────

interface BlockEditorProps {
  html: string;
  onChange: (html: string) => void;
  label?: string;
}

export function BlockEditor({ html, onChange, label }: BlockEditorProps) {
  const [blocks, setBlocks] = useState<Block[]>(() => htmlToBlocks(html));

  const handleChange = (updated: Block[]) => {
    setBlocks(updated);
    onChange(blocksToHtml(updated));
  };

  const updateTextBlock = (id: string, text: string) => {
    handleChange(blocks.map((b) => (b.id === id ? { ...b, text } : b)));
  };

  const updateListItem = (blockId: string, itemId: string, text: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || (b.type !== 'ul' && b.type !== 'ol')) return b;
        return { ...b, items: b.items.map((item) => (item.id === itemId ? { ...item, text } : item)) };
      }),
    );
  };

  const addListItem = (blockId: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || (b.type !== 'ul' && b.type !== 'ol')) return b;
        return { ...b, items: [...b.items, { id: crypto.randomUUID(), text: '', attrs: '' }] };
      }),
    );
  };

  const removeListItem = (blockId: string, itemId: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || (b.type !== 'ul' && b.type !== 'ol')) return b;
        const filtered = b.items.filter((item) => item.id !== itemId);
        return { ...b, items: filtered.length > 0 ? filtered : b.items };
      }),
    );
  };

  const updateTableCell = (blockId: string, rowId: string, cellId: string, text: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || b.type !== 'table') return b;
        return {
          ...b,
          rows: b.rows.map((row) =>
            row.id !== rowId
              ? row
              : { ...row, cells: row.cells.map((cell) => (cell.id !== cellId ? cell : { ...cell, text })) },
          ),
        };
      }),
    );
  };

  const addTableRow = (blockId: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || b.type !== 'table') return b;
        const colCount = b.rows[0]?.cells.length ?? 1;
        const newRow: TableRow = {
          id: crypto.randomUUID(),
          attrs: '',
          cells: Array.from({ length: colCount }, () => ({ id: crypto.randomUUID(), text: '', isHeader: false, attrs: '' })),
        };
        return { ...b, rows: [...b.rows, newRow] };
      }),
    );
  };

  const removeTableRow = (blockId: string, rowId: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || b.type !== 'table') return b;
        const filtered = b.rows.filter((r) => r.id !== rowId);
        return { ...b, rows: filtered.length > 0 ? filtered : b.rows };
      }),
    );
  };

  const addTableColumn = (blockId: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || b.type !== 'table') return b;
        return {
          ...b,
          rows: b.rows.map((row, rowIdx) => ({
            ...row,
            cells: [
              ...row.cells,
              { id: crypto.randomUUID(), text: '', isHeader: rowIdx === 0 && row.cells[0]?.isHeader, attrs: '' },
            ],
          })),
        };
      }),
    );
  };

  const removeTableColumn = (blockId: string, colIndex: number) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || b.type !== 'table') return b;
        return {
          ...b,
          rows: b.rows.map((row) => ({
            ...row,
            cells: row.cells.filter((_, i) => i !== colIndex),
          })),
        };
      }),
    );
  };

  const HEADING_CLASS: Record<string, string> = {
    h1: 'text-xl font-bold',
    h2: 'text-lg font-semibold',
    h3: 'text-base font-semibold',
    h4: 'text-sm font-semibold',
  };

  return (
    <div className="space-y-3">
      {label && <p className="text-sm font-medium text-foreground">{label}</p>}
      {blocks.map((block) => {
        // ── Table ──
        if (block.type === 'table') {
          const colCount = block.rows[0]?.cells.length ?? 0;
          return (
            <div key={block.id} className="border border-border rounded-md overflow-hidden">
              <div className="flex items-center justify-between px-3 py-1.5 bg-muted/40 border-b border-border">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Table</p>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" className="text-xs h-6 px-2" onClick={() => addTableColumn(block.id)} type="button">
                    <Plus className="h-3 w-3 mr-1" />Col
                  </Button>
                  {colCount > 1 && (
                    <Button variant="ghost" size="sm" className="text-xs h-6 px-2 text-muted-foreground hover:text-destructive" onClick={() => removeTableColumn(block.id, colCount - 1)} type="button">
                      <X className="h-3 w-3 mr-1" />Col
                    </Button>
                  )}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <tbody>
                    {block.rows.map((row, rowIdx) => (
                      <tr
                        key={row.id}
                        className={cn(
                          row.cells[0]?.isHeader
                            ? 'bg-[hsl(222_47%_15%)]'
                            : rowIdx % 2 === 0 ? 'bg-white' : 'bg-[hsl(214_32%_97%)]'
                        )}
                      >
                        {row.cells.map((cell) => (
                          <td
                            key={cell.id}
                            className={cn(
                              'border p-0',
                              cell.isHeader ? 'border-[hsl(222_47%_22%)]' : 'border-border',
                            )}
                          >
                            <Input
                              value={cell.text}
                              onChange={(e) => updateTableCell(block.id, row.id, cell.id, e.target.value)}
                              className={cn(
                                'border-0 rounded-none h-9 focus-visible:ring-inset focus-visible:ring-1',
                                cell.isHeader
                                  ? 'bg-transparent text-white placeholder:text-white/50 font-semibold'
                                  : 'bg-transparent',
                              )}
                              placeholder={cell.isHeader ? 'Header...' : 'Cell...'}
                            />
                          </td>
                        ))}
                        <td className="border-0 w-7 pl-1">
                          {rowIdx > 0 && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-muted-foreground hover:text-destructive"
                              onClick={() => removeTableRow(block.id, row.id)}
                              type="button"
                            >
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="px-3 py-2 border-t border-border bg-muted/20">
                <Button variant="ghost" size="sm" className="text-xs text-muted-foreground h-7" onClick={() => addTableRow(block.id)} type="button">
                  <Plus className="h-3.5 w-3.5 mr-1" />
                  Add row
                </Button>
              </div>
            </div>
          );
        }

        // ── List ──
        if (block.type === 'ul' || block.type === 'ol') {
          return (
            <div key={block.id} className="border border-border rounded-md p-3 space-y-2 bg-muted/20">
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {block.type === 'ul' ? 'Bullet List' : 'Numbered List'}
              </p>
              {block.items.map((item, idx) => (
                <div key={item.id} className="flex items-center gap-2">
                  <span className="text-muted-foreground text-sm w-4 shrink-0 select-none">
                    {block.type === 'ul' ? '•' : `${idx + 1}.`}
                  </span>
                  <Input
                    value={item.text}
                    onChange={(e) => updateListItem(block.id, item.id, e.target.value)}
                    className="flex-1"
                    placeholder="List item..."
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                    onClick={() => removeListItem(block.id, item.id)}
                    type="button"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
              <Button variant="ghost" size="sm" className="text-xs text-muted-foreground" onClick={() => addListItem(block.id)} type="button">
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add item
              </Button>
            </div>
          );
        }

        // ── Heading ──
        if (['h1', 'h2', 'h3', 'h4'].includes(block.type)) {
          return (
            <div key={block.id} className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">{block.type.toUpperCase()}</p>
              <Input
                value={block.text}
                onChange={(e) => updateTextBlock(block.id, e.target.value)}
                className={cn(HEADING_CLASS[block.type])}
                placeholder={`${block.type.toUpperCase()} text...`}
              />
            </div>
          );
        }

        // ── Paragraph / Blockquote ──
        return (
          <div key={block.id} className="space-y-1">
            {block.type === 'blockquote' && (
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Callout</p>
            )}
            <Textarea
              value={block.text}
              onChange={(e) => updateTextBlock(block.id, e.target.value)}
              className={cn(
                'resize-y',
                block.type === 'blockquote' && 'border-l-4 border-l-primary rounded-l-none italic',
              )}
              rows={Math.max(2, Math.ceil((block.text.length || 0) / 100))}
              placeholder="Paragraph text..."
            />
          </div>
        );
      })}
    </div>
  );
}
