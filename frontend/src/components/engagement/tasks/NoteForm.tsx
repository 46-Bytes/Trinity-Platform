import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Check, ChevronDown, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { NOTE_TYPES, NoteTypeIndicator } from '@/components/engagement/notes/NoteCard';
import type { NoteCreatePayload, NoteType } from '@/store/slices/notesReducer';

const noteFormSchema = z.object({
  content: z.string().min(1, 'Content is required'),
  noteType: z.enum(['general', 'follow_up', 'issue', 'decision']).optional(),
});

type NoteFormValues = z.infer<typeof noteFormSchema>;

interface NoteFormProps {
  engagementId: string;
  taskId?: string;
  initialValues?: {
    content?: string;
    noteType?: NoteType;
  };
  isEditing?: boolean;
  onSubmit: (data: NoteCreatePayload) => void;
  onCancel: () => void;
  /** 'bordered' = labeled fields (default, task notes). 'minimal' = borderless composer (engagement notes modal). */
  variant?: 'bordered' | 'minimal';
}

export function NoteForm({ engagementId, taskId, initialValues, isEditing, onSubmit, onCancel, variant = 'bordered' }: NoteFormProps) {
  const form = useForm<NoteFormValues>({
    resolver: zodResolver(noteFormSchema),
    defaultValues: {
      content: initialValues?.content ?? '',
      noteType: initialValues?.noteType ?? 'general',
    },
  });

  const handleSubmit = (values: NoteFormValues) => {
    onSubmit({
      engagementId,
      taskId,
      content: values.content,
      noteType: values.noteType,
      visibility: 'all',
    } as NoteCreatePayload);
  };

  if (variant === 'minimal') {
    return (
      <Form {...form}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            e.stopPropagation();
            form.handleSubmit(handleSubmit)(e);
          }}
          className="flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              {isEditing ? 'Edit note' : 'New note'}
            </span>
            <button
              type="button"
              onClick={onCancel}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <FormField
            control={form.control}
            name="content"
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <Textarea
                    placeholder="Write your note..."
                    {...field}
                    autoFocus
                    className="min-h-[320px] resize-none border-none shadow-none px-0 text-base focus-visible:ring-0"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="flex items-center justify-between pt-3 border-t mt-3">
            <FormField
              control={form.control}
              name="noteType"
              render={({ field }) => (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button type="button" className="inline-flex items-center gap-1">
                      <NoteTypeIndicator noteType={field.value ?? 'general'} />
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start">
                    {NOTE_TYPES.map((t) => (
                      <DropdownMenuItem
                        key={t.value}
                        onClick={() => field.onChange(t.value)}
                        className="flex items-center justify-between gap-4"
                      >
                        <NoteTypeIndicator noteType={t.value} />
                        {field.value === t.value && <Check className="h-4 w-4 text-success" />}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            />
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={onCancel}>
                Cancel
              </Button>
              <Button type="submit" size="sm" className="bg-success text-success-foreground hover:bg-success/90">
                Save note
              </Button>
            </div>
          </div>
        </form>
      </Form>
    );
  }

  return (
    <Form {...form}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          e.stopPropagation();
          form.handleSubmit(handleSubmit)(e);
        }}
        className="space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <FormField
          control={form.control}
          name="content"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Content</FormLabel>
              <FormControl>
                <Textarea placeholder="Enter note content" {...field} rows={6} autoFocus />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="noteType"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Note Type</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {NOTE_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />


        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" className="bg-success text-success-foreground hover:bg-success/90">
            {isEditing ? 'Save Note' : 'Create Note'}
          </Button>
        </div>
      </form>
    </Form>
  );
}
