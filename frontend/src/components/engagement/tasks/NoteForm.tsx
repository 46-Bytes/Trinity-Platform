import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import type { NoteCreatePayload } from '@/store/slices/notesReducer';

const noteFormSchema = z.object({
  title: z.string().min(1, 'Title is required').max(255, 'Title must be less than 255 characters'),
  content: z.string().min(1, 'Content is required'),
  noteType: z.enum(['general', 'meeting', 'observation', 'decision', 'progress_update']).optional(),
});

type NoteFormValues = z.infer<typeof noteFormSchema>;

interface NoteFormProps {
  engagementId: string;
  taskId?: string;
  initialValues?: {
    title?: string;
    content?: string;
    noteType?: 'general' | 'meeting' | 'observation' | 'decision' | 'progress_update';
  };
  isEditing?: boolean;
  onSubmit: (data: NoteCreatePayload) => void;
  onCancel: () => void;
}

export function NoteForm({ engagementId, taskId, initialValues, isEditing, onSubmit, onCancel }: NoteFormProps) {
  const form = useForm<NoteFormValues>({
    resolver: zodResolver(noteFormSchema),
    defaultValues: {
      title: initialValues?.title ?? '',
      content: initialValues?.content ?? '',
      noteType: initialValues?.noteType ?? 'general',
    },
  });

  const handleSubmit = (values: NoteFormValues) => {
    onSubmit({
      engagementId,
      taskId,
      title: values.title,
      content: values.content,
      noteType: values.noteType,
      visibility: 'all',
    } as NoteCreatePayload);
  };

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
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input placeholder="Enter note title" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="content"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Content *</FormLabel>
              <FormControl>
                <Textarea placeholder="Enter note content" {...field} rows={6} />
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
                  <SelectItem value="general">General</SelectItem>
                  <SelectItem value="meeting">Meeting</SelectItem>
                  <SelectItem value="observation">Observation</SelectItem>
                  <SelectItem value="decision">Decision</SelectItem>
                  <SelectItem value="progress_update">Progress Update</SelectItem>
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

