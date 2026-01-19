import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Switch } from '@/components/ui/switch';
import type { NoteCreatePayload } from '@/store/slices/notesReducer';

const noteFormSchema = z.object({
  title: z.string().max(255, 'Title must be less than 255 characters').optional(),
  content: z.string().min(1, 'Content is required'),
  noteType: z.enum(['general', 'meeting', 'observation', 'decision', 'progress_update']).optional(),
  visibility: z.enum(['all', 'advisor_only', 'client_only']).optional(),
});

type NoteFormValues = z.infer<typeof noteFormSchema>;

interface NoteFormProps {
  engagementId: string;
  taskId?: string;
  onSubmit: (data: NoteCreatePayload) => void;
  onCancel: () => void;
}

export function NoteForm({ engagementId, taskId, onSubmit, onCancel }: NoteFormProps) {
  const form = useForm<NoteFormValues>({
    resolver: zodResolver(noteFormSchema),
    defaultValues: {
      title: '',
      content: '',
      noteType: 'general',
      visibility: 'all',
    },
  });

  const handleSubmit = (values: NoteFormValues) => {
    onSubmit({
      engagementId,
      taskId,
      title: values.title || undefined,
      content: values.content,
      noteType: values.noteType,
      visibility: values.visibility,
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
              <FormLabel>Title (Optional)</FormLabel>
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

        <div className="grid grid-cols-2 gap-4">
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

          <FormField
            control={form.control}
            name="visibility"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Visibility</FormLabel>
                <Select onValueChange={field.onChange} defaultValue={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select visibility" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="advisor_only">Advisor Only</SelectItem>
                    <SelectItem value="client_only">Client Only</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>


        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit">Create Note</Button>
        </div>
      </form>
    </Form>
  );
}

