import { Info } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { ModuleNote, ModuleTable } from '@/store/slices/programGuideReducer';

/**
 * Authored prose, rendered with its paragraph breaks intact.
 *
 * Note and detail text carries real "\n\n" breaks - several run to three or four
 * paragraphs - and collapsing them into one block makes the longer guardrail and
 * purpose notes close to unreadable. `whitespace-pre-line` would do it in one
 * class, but splitting gives each paragraph its own spacing, which matches the
 * rest of the card.
 */
export function Prose({ text, className }: { text: string; className?: string }) {
  const paragraphs = text.split(/\n{2,}/).filter(Boolean);
  return (
    <div className={cn('space-y-2', className)}>
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="text-sm leading-relaxed text-muted-foreground whitespace-pre-line">
          {paragraph}
        </p>
      ))}
    </div>
  );
}

/**
 * Notes for one section of the card.
 *
 * A note may be titled or untitled, and may carry a list of its own alongside
 * its prose. All four combinations occur in the seeded content, so none of them
 * is special-cased away.
 */
export function NoteBlocks({ notes, className }: { notes: ModuleNote[]; className?: string }) {
  if (notes.length === 0) return null;

  return (
    <div className={cn('space-y-3', className)}>
      {notes.map((note) => (
        <div key={note.key} className="rounded-lg border-l-2 border-primary/40 bg-muted/40 px-4 py-3">
          {note.title && (
            <p className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-foreground">
              <Info className="h-3.5 w-3.5 flex-shrink-0 text-primary" />
              {note.title}
            </p>
          )}
          <Prose text={note.text} />
          {note.items && note.items.length > 0 && (
            <ul className="mt-2 space-y-1.5">
              {note.items.map((item, index) => (
                <li key={index} className="relative pl-4 text-sm leading-relaxed text-muted-foreground">
                  <span className="absolute left-0 top-[0.6rem] h-1 w-1 rounded-full bg-muted-foreground/50" />
                  {item}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * A reference matrix, such as V7's four business-model shapes against nine
 * dimensions.
 *
 * Cells align to columns by index, and a short row is padded rather than
 * shifting the remaining cells left under the wrong headings. The wrapper
 * scrolls on its own so a wide matrix never makes the page scroll sideways.
 */
export function ReferenceTable({ table }: { table: ModuleTable }) {
  return (
    <div className="space-y-2">
      {table.title && <p className="text-sm font-semibold text-foreground">{table.title}</p>}
      {table.intro && <Prose text={table.intro} />}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="bg-muted/50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground" />
              {table.columns.map((column) => (
                <th
                  key={column.key}
                  className="bg-muted/50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => (
              <tr key={row.key} className="border-t border-border/60 align-top">
                <th scope="row" className="px-3 py-2.5 text-left text-xs font-semibold text-foreground">
                  {row.label}
                </th>
                {table.columns.map((column, index) => (
                  <td key={column.key} className="px-3 py-2.5 text-sm leading-relaxed text-muted-foreground">
                    {row.cells[index] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** The bulleted list used by every prose section on the card. */
export function BulletList({
  items,
  variant = 'default',
}: {
  items: string[];
  variant?: 'default' | 'positive' | 'negative';
}) {
  const dot = {
    default: 'bg-muted-foreground/40',
    positive: 'bg-success',
    negative: 'bg-destructive',
  }[variant];

  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={index} className="relative pl-4 text-sm leading-relaxed text-muted-foreground">
          <span className={cn('absolute left-0 top-[0.6rem] h-1.5 w-1.5 rounded-full', dot)} />
          {item}
        </li>
      ))}
    </ul>
  );
}
