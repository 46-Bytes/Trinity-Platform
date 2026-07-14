import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchCategoriesWithVideos } from '@/store/slices/helpReducer';
import { YouTubePlayer } from '@/components/help/YouTubePlayer';
import { Loader2, Settings, PlayCircle } from 'lucide-react';
import { toast } from 'sonner';

export default function HelpPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { categories, isLoading, error } = useAppSelector((state) => state.help);

  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin';

  useEffect(() => {
    dispatch(fetchCategoriesWithVideos());
  }, [dispatch]);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const hasContent = categories.some((c) => c.videos.length > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Help &amp; User Guide</h1>
          <p className="text-muted-foreground mt-1">
            Watch training and walkthrough videos to learn how to use Trinity.
          </p>
        </div>
        {isAdmin && (
          <button className="btn-primary" onClick={() => navigate('/dashboard/help/manage')}>
            <Settings className="w-4 h-4" />
            Manage videos
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading videos...</span>
        </div>
      ) : !hasContent ? (
        <div className="card-trinity p-12 text-center">
          <PlayCircle className="w-10 h-10 mx-auto text-muted-foreground/50" />
          <p className="text-muted-foreground mt-3">No help videos are available yet.</p>
          {isAdmin && (
            <p className="text-sm text-muted-foreground mt-1">
              Use “Manage videos” to add your first category and video.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-10">
          {categories
            .filter((category) => category.videos.length > 0)
            .map((category) => (
              <section key={category.id} className="space-y-4">
                <div>
                  <h2 className="font-heading text-xl font-semibold text-foreground">{category.name}</h2>
                  {category.description && (
                    <p className="text-muted-foreground mt-1">{category.description}</p>
                  )}
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {category.videos.map((video) => (
                    <div key={video.id} className="card-trinity p-4 space-y-3">
                      <YouTubePlayer videoId={video.youtube_video_id} title={video.title} />
                      <div>
                        <h3 className="font-medium text-foreground">{video.title}</h3>
                        {video.description && (
                          <p className="text-sm text-muted-foreground mt-1">{video.description}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ))}
        </div>
      )}
    </div>
  );
}
