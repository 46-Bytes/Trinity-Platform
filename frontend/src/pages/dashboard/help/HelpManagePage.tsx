import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchCategoriesWithVideos,
  createCategory,
  updateCategory,
  deleteCategory,
  reorderCategories,
  createVideo,
  updateVideo,
  deleteVideo,
  reorderVideos,
} from '@/store/slices/helpReducer';
import { extractYouTubeId } from '@/lib/youtube';
import { YouTubePlayer } from '@/components/help/YouTubePlayer';
import type { CategoryWithVideos, HelpVideo } from '@/types/help';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ArrowLeft,
  Plus,
  ChevronUp,
  ChevronDown,
  Edit,
  Trash2,
  Loader2,
  FolderPlus,
} from 'lucide-react';
import { toast } from 'sonner';

type DeleteTarget =
  | { type: 'category'; id: string; name: string }
  | { type: 'video'; id: string; name: string };

/** Return a new array of ids with the item at `index` moved by `dir` (-1 up / +1 down). */
function reorderedIds<T extends { id: string }>(items: T[], index: number, dir: -1 | 1): string[] | null {
  const target = index + dir;
  if (target < 0 || target >= items.length) return null;
  const ids = items.map((i) => i.id);
  [ids[index], ids[target]] = [ids[target], ids[index]];
  return ids;
}

export default function HelpManagePage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { categories, isLoading, isSaving, error } = useAppSelector((state) => state.help);

  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin';

  // Category dialog state
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<CategoryWithVideos | null>(null);
  const [categoryName, setCategoryName] = useState('');
  const [categoryDescription, setCategoryDescription] = useState('');

  // Video dialog state
  const [videoDialogOpen, setVideoDialogOpen] = useState(false);
  const [editingVideo, setEditingVideo] = useState<HelpVideo | null>(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [videoTitle, setVideoTitle] = useState('');
  const [videoDescription, setVideoDescription] = useState('');
  const [videoCategoryId, setVideoCategoryId] = useState('');

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);

  const previewId = useMemo(() => extractYouTubeId(videoUrl), [videoUrl]);
  const selectedCategoryName = categories.find((c) => c.id === videoCategoryId)?.name ?? '';

  useEffect(() => {
    if (!isAdmin) {
      navigate('/dashboard/help', { replace: true });
      return;
    }
    dispatch(fetchCategoriesWithVideos());
  }, [dispatch, isAdmin, navigate]);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  if (!isAdmin) return null;

  const refresh = () => dispatch(fetchCategoriesWithVideos());

  // ------------------------------ Categories ------------------------------

  const openAddCategory = () => {
    setEditingCategory(null);
    setCategoryName('');
    setCategoryDescription('');
    setCategoryDialogOpen(true);
  };

  const openEditCategory = (category: CategoryWithVideos) => {
    setEditingCategory(category);
    setCategoryName(category.name);
    setCategoryDescription(category.description ?? '');
    setCategoryDialogOpen(true);
  };

  const submitCategory = async () => {
    if (!categoryName.trim()) {
      toast.error('Category name is required');
      return;
    }
    try {
      if (editingCategory) {
        await dispatch(
          updateCategory({
            id: editingCategory.id,
            name: categoryName.trim(),
            description: categoryDescription.trim() || undefined,
          })
        ).unwrap();
        toast.success('Category updated');
      } else {
        await dispatch(
          createCategory({ name: categoryName.trim(), description: categoryDescription.trim() || undefined })
        ).unwrap();
        toast.success('Category created');
      }
      setCategoryDialogOpen(false);
      refresh();
    } catch {
      // error surfaced via the error toast effect
    }
  };

  const moveCategory = async (index: number, dir: -1 | 1) => {
    const ids = reorderedIds(categories, index, dir);
    if (!ids) return;
    try {
      await dispatch(reorderCategories(ids)).unwrap();
      refresh();
    } catch {
      /* handled */
    }
  };

  // -------------------------------- Videos --------------------------------

  const openAddVideo = (categoryId: string) => {
    setEditingVideo(null);
    setVideoUrl('');
    setVideoTitle('');
    setVideoDescription('');
    setVideoCategoryId(categoryId);
    setVideoDialogOpen(true);
  };

  const openEditVideo = (video: HelpVideo) => {
    setEditingVideo(video);
    setVideoUrl('');
    setVideoTitle(video.title);
    setVideoDescription(video.description ?? '');
    setVideoCategoryId(video.category_id);
    setVideoDialogOpen(true);
  };

  const submitVideo = async () => {
    if (!videoTitle.trim()) {
      toast.error('Video title is required');
      return;
    }
    if (!videoCategoryId) {
      toast.error('Please select a category');
      return;
    }
    // URL required when creating; optional when editing (blank = keep existing).
    if (!editingVideo && !previewId) {
      toast.error('Please enter a valid YouTube URL');
      return;
    }
    if (videoUrl.trim() && !previewId) {
      toast.error('That YouTube URL is not valid');
      return;
    }

    try {
      if (editingVideo) {
        await dispatch(
          updateVideo({
            id: editingVideo.id,
            title: videoTitle.trim(),
            description: videoDescription.trim() || undefined,
            category_id: videoCategoryId,
            youtube_url: videoUrl.trim() || undefined,
          })
        ).unwrap();
        toast.success('Video updated');
      } else {
        await dispatch(
          createVideo({
            category_id: videoCategoryId,
            youtube_url: videoUrl.trim(),
            title: videoTitle.trim(),
            description: videoDescription.trim() || undefined,
          })
        ).unwrap();
        toast.success('Video added');
      }
      setVideoDialogOpen(false);
      refresh();
    } catch {
      /* handled */
    }
  };

  const moveVideo = async (category: CategoryWithVideos, index: number, dir: -1 | 1) => {
    const ids = reorderedIds(category.videos, index, dir);
    if (!ids) return;
    try {
      await dispatch(reorderVideos({ categoryId: category.id, orderedIds: ids })).unwrap();
      refresh();
    } catch {
      /* handled */
    }
  };

  // -------------------------------- Delete --------------------------------

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.type === 'category') {
        await dispatch(deleteCategory(deleteTarget.id)).unwrap();
        toast.success('Category deleted');
      } else {
        await dispatch(deleteVideo(deleteTarget.id)).unwrap();
        toast.success('Video deleted');
      }
      setDeleteTarget(null);
      refresh();
    } catch {
      /* handled */
    }
  };

  // -------------------------------- Render --------------------------------

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="space-y-1">
          <button
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => navigate('/dashboard/help')}
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Help
          </button>
          <h1 className="font-heading text-2xl font-bold text-foreground">Manage Help Videos</h1>
          <p className="text-muted-foreground">Add, edit, reorder, and remove categories and videos.</p>
        </div>
        <button className="btn-primary" onClick={openAddCategory}>
          <FolderPlus className="w-4 h-4" />
          Add Category
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading...</span>
        </div>
      ) : categories.length === 0 ? (
        <div className="card-trinity p-12 text-center">
          <FolderPlus className="w-10 h-10 mx-auto text-muted-foreground/50" />
          <p className="text-muted-foreground mt-3">No categories yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {categories.map((category, catIndex) => (
            <div key={category.id} className="card-trinity p-5 space-y-4">
              {/* Category header */}
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="font-heading text-lg font-semibold text-foreground truncate">
                    {category.name}
                  </h2>
                  {category.description && (
                    <p className="text-sm text-muted-foreground mt-0.5">{category.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    className="p-1.5 rounded-lg hover:bg-muted disabled:opacity-40 transition-colors"
                    onClick={() => moveCategory(catIndex, -1)}
                    disabled={catIndex === 0 || isSaving}
                    aria-label="Move category up"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                  <button
                    className="p-1.5 rounded-lg hover:bg-muted disabled:opacity-40 transition-colors"
                    onClick={() => moveCategory(catIndex, 1)}
                    disabled={catIndex === categories.length - 1 || isSaving}
                    aria-label="Move category down"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  <button
                    className="p-1.5 rounded-lg hover:bg-muted transition-colors"
                    onClick={() => openEditCategory(category)}
                    aria-label="Edit category"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    className="p-1.5 rounded-lg hover:bg-muted text-destructive transition-colors"
                    onClick={() => setDeleteTarget({ type: 'category', id: category.id, name: category.name })}
                    aria-label="Delete category"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Videos */}
              <div className="space-y-2">
                {category.videos.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic">No videos in this category yet.</p>
                ) : (
                  category.videos.map((video, vidIndex) => (
                    <div
                      key={video.id}
                      className="flex items-center justify-between gap-3 rounded-lg border border-border p-3"
                    >
                      <div className="min-w-0">
                        <p className="font-medium text-foreground truncate">{video.title}</p>
                        <p className="text-xs text-muted-foreground truncate">
                          youtu.be/{video.youtube_video_id}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          className="p-1.5 rounded-lg hover:bg-muted disabled:opacity-40 transition-colors"
                          onClick={() => moveVideo(category, vidIndex, -1)}
                          disabled={vidIndex === 0 || isSaving}
                          aria-label="Move video up"
                        >
                          <ChevronUp className="w-4 h-4" />
                        </button>
                        <button
                          className="p-1.5 rounded-lg hover:bg-muted disabled:opacity-40 transition-colors"
                          onClick={() => moveVideo(category, vidIndex, 1)}
                          disabled={vidIndex === category.videos.length - 1 || isSaving}
                          aria-label="Move video down"
                        >
                          <ChevronDown className="w-4 h-4" />
                        </button>
                        <button
                          className="p-1.5 rounded-lg hover:bg-muted transition-colors"
                          onClick={() => openEditVideo(video)}
                          aria-label="Edit video"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          className="p-1.5 rounded-lg hover:bg-muted text-destructive transition-colors"
                          onClick={() => setDeleteTarget({ type: 'video', id: video.id, name: video.title })}
                          aria-label="Delete video"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
                <Button variant="outline" size="sm" onClick={() => openAddVideo(category.id)}>
                  <Plus className="w-4 h-4 mr-1" />
                  Add Video
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Category dialog */}
      <Dialog open={categoryDialogOpen} onOpenChange={setCategoryDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{editingCategory ? 'Edit Category' : 'Add Category'}</DialogTitle>
            <DialogDescription>Categories group videos on the Help page.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="category-name">Name *</Label>
              <Input
                id="category-name"
                placeholder="Getting Started"
                value={categoryName}
                onChange={(e) => setCategoryName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="category-description">Description</Label>
              <Textarea
                id="category-description"
                placeholder="Optional short description"
                value={categoryDescription}
                onChange={(e) => setCategoryDescription(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={() => setCategoryDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitCategory} disabled={isSaving || !categoryName.trim()}>
              {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              {editingCategory ? 'Save' : 'Create'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Video dialog */}
      <Dialog open={videoDialogOpen} onOpenChange={setVideoDialogOpen}>
        <DialogContent className="sm:max-w-[560px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingVideo ? 'Edit Video' : 'Add Video'}</DialogTitle>
            <DialogDescription>
              Paste a YouTube URL — Trinity extracts and stores the video ID.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="video-url">
                YouTube URL {editingVideo ? '(leave blank to keep current)' : '*'}
              </Label>
              <Input
                id="video-url"
                placeholder="https://www.youtube.com/watch?v=..."
                value={videoUrl}
                onChange={(e) => setVideoUrl(e.target.value)}
              />
              {videoUrl.trim() && !previewId && (
                <p className="text-xs text-destructive">Not a valid YouTube URL.</p>
              )}
            </div>

            {previewId ? (
              <YouTubePlayer videoId={previewId} title="Preview" />
            ) : editingVideo ? (
              <YouTubePlayer videoId={editingVideo.youtube_video_id} title="Current video" />
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="video-title">Title *</Label>
              <Input
                id="video-title"
                placeholder="How to run a diagnostic"
                value={videoTitle}
                onChange={(e) => setVideoTitle(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="video-description">Description</Label>
              <Textarea
                id="video-description"
                placeholder="Optional short description"
                value={videoDescription}
                onChange={(e) => setVideoDescription(e.target.value)}
              />
            </div>
            {editingVideo ? (
              // Editing: allow moving the video to a different category.
              <div className="space-y-2">
                <Label htmlFor="video-category">Category *</Label>
                <Select value={videoCategoryId} onValueChange={setVideoCategoryId}>
                  <SelectTrigger id="video-category">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : (
              // Adding within a category: category is fixed by context, shown read-only.
              <div className="space-y-2">
                <Label>Category</Label>
                <div className="rounded-md border border-input bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                  {selectedCategoryName}
                </div>
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={() => setVideoDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitVideo} disabled={isSaving || !videoTitle.trim() || !videoCategoryId}>
              {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              {editingVideo ? 'Save' : 'Add Video'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {deleteTarget?.type === 'category' ? 'Category' : 'Video'}</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete{' '}
              <span className="font-semibold">{deleteTarget?.name}</span>?
              {deleteTarget?.type === 'category' && ' All videos in this category will also be removed.'}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={isSaving}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={isSaving}>
              {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
