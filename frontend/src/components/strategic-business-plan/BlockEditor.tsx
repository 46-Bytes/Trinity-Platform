import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Plus, X } from 'lucide-react';

type TextBlock = {
  id: string;
  type: 'h1' | 'h2' | 'h3' | 'h4' | 'p' | 'blockquote';
  html: string;
};

type ListBlock = {
  id: string;
  type: 'ul' | 'ol';
  items: { id: string; html: string }[];
};

type Block = TextBlock | ListBlock;

function htmlToBlocks(html: string): Block[] {
  const doc = new DOMParser().parseFromString(`<div id="root">${html}</div>`, 'text/html');
  const root = doc.getElementById('root');
  if (!root) return [];

  const blocks: Block[] = [];

  root.childNodes.forEach((node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent?.trim();
      if (text) {
        blocks.push({ id: crypto.randomUUID(), type: 'p', html: text });
      }
      return;
    }

    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const el = node as Element;
    const tag = el.tagName.toLowerCase();

    if (['h1', 'h2', 'h3', 'h4'].includes(tag)) {
      blocks.push({ id: crypto.randomUUID(), type: tag as TextBlock['type'], html: el.innerHTML });
      return;
    }

    if (tag === 'p' || tag === 'blockquote') {
      blocks.push({ id: crypto.randomUUID(), type: tag as TextBlock['type'], html: el.innerHTML });
      return;
    }

    if (tag === 'ul' || tag === 'ol') {
      const items = Array.from(el.querySelectorAll(':scope > li')).map((li) => ({
        id: crypto.randomUUID(),
        html: li.innerHTML,
      }));
      if (items.length > 0) {
        blocks.push({ id: crypto.randomUUID(), type: tag as ListBlock['type'], items });
      }
      return;
    }

    // Unknown tag — preserve as opaque paragraph so nothing is dropped
    blocks.push({ id: crypto.randomUUID(), type: 'p', html: el.outerHTML });
  });

  return blocks;
}

function blocksToHtml(blocks: Block[]): string {
  return blocks
    .map((block) => {
      if (block.type === 'ul' || block.type === 'ol') {
        const items = block.items.map((item) => `<li>${item.html}</li>`).join('');
        return `<${block.type}>${items}</${block.type}>`;
      }
      return `<${block.type}>${block.html}</${block.type}>`;
    })
    .join('\n');
}

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

  const updateTextBlock = (id: string, newHtml: string) => {
    handleChange(blocks.map((b) => (b.id === id ? { ...b, html: newHtml } : b)));
  };

  const updateListItem = (blockId: string, itemId: string, newHtml: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || (b.type !== 'ul' && b.type !== 'ol')) return b;
        return { ...b, items: b.items.map((item) => (item.id === itemId ? { ...item, html: newHtml } : item)) };
      }),
    );
  };

  const addListItem = (blockId: string) => {
    handleChange(
      blocks.map((b) => {
        if (b.id !== blockId || (b.type !== 'ul' && b.type !== 'ol')) return b;
        return { ...b, items: [...b.items, { id: crypto.randomUUID(), html: '' }] };
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
                    value={item.html}
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
              <Button
                variant="ghost"
                size="sm"
                className="text-xs text-muted-foreground"
                onClick={() => addListItem(block.id)}
                type="button"
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add item
              </Button>
            </div>
          );
        }

        if (['h1', 'h2', 'h3', 'h4'].includes(block.type)) {
          return (
            <div key={block.id} className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">{block.type.toUpperCase()}</p>
              <Input
                value={block.html}
                onChange={(e) => updateTextBlock(block.id, e.target.value)}
                className={cn(HEADING_CLASS[block.type])}
                placeholder={`${block.type.toUpperCase()} text...`}
              />
            </div>
          );
        }

        // Paragraph / blockquote
        return (
          <div key={block.id} className="space-y-1">
            {block.type === 'blockquote' && (
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Callout</p>
            )}
            <Textarea
              value={block.html}
              onChange={(e) => updateTextBlock(block.id, e.target.value)}
              className={cn(
                'resize-y',
                block.type === 'blockquote' && 'border-l-4 border-l-primary rounded-l-none italic',
              )}
              rows={Math.max(2, Math.ceil((block.html.length || 0) / 100))}
              placeholder="Paragraph text..."
            />
          </div>
        );
      })}
    </div>
  );
}
