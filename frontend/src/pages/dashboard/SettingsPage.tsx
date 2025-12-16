import { useEffect, useState, useRef } from 'react';
import { useAuth } from '@/context/AuthContext';
import { User, Lock, Bell, Palette, Globe, Shield, Save } from 'lucide-react';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const tabs = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'security', label: 'Security', icon: Lock },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'appearance', label: 'Appearance', icon: Palette },
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('profile');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [bio, setBio] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Initialize form fields from current user
  useEffect(() => {
    if (user) {
      const nameParts = (user.name || '').split(' ');
      setFirstName(nameParts[0] || '');
      setLastName(nameParts.slice(1).join(' ') || '');
      setEmail(user.email || '');
      // bio is optional and may not exist on the typed User object
      const anyUser: any = user;
      setBio(anyUser.bio || '');
      setPreviewUrl(user.avatar || null);
    }
  }, [user]);

  const handlePhotoClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const formData = new FormData();
      formData.append('first_name', firstName);
      formData.append('last_name', lastName);
      formData.append('email', email);
      formData.append('bio', bio);

      const file = fileInputRef.current?.files?.[0];
      if (file) {
        formData.append('profile_picture', file);
      }

      const response = await fetch(`${API_BASE_URL}/api/settings/profile`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to save profile');
      }

      const data = await response.json();
      // For now, simplest is to refresh user data by reloading
      setSuccess('Profile updated successfully');
      // Optional: window.location.reload();
    } catch (err) {
      console.error('Failed to save profile', err);
      setError(err instanceof Error ? err.message : 'Failed to save profile');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-heading text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your account and preferences</p>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar */}
        <div className="lg:w-64 flex-shrink-0">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors",
                  activeTab === tab.id 
                    ? "bg-accent/10 text-accent font-medium" 
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <tab.icon className="w-5 h-5" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === 'profile' && (
            <form className="card-trinity p-6 space-y-6" onSubmit={handleSaveProfile}>
              <div>
                <h2 className="font-heading text-lg font-semibold mb-1">Profile Information</h2>
                <p className="text-sm text-muted-foreground">Update your personal details</p>
              </div>

              <div className="flex items-center gap-6">
                <div className="w-20 h-20 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-2xl font-semibold overflow-hidden">
                  {previewUrl || user?.avatar ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={previewUrl || user?.avatar}
                      alt="Profile"
                      className="w-20 h-20 rounded-full object-cover"
                      onError={(e) => {
                        // Fallback to initial if image fails to load
                        const target = e.target as HTMLImageElement;
                        target.style.display = 'none';
                        const parent = target.parentElement;
                        if (parent) {
                          parent.textContent = user?.name.charAt(0) || '';
                        }
                      }}
                    />
                  ) : (
                    user?.name.charAt(0)
                  )}
                </div>
                <div>
                  <button
                    type="button"
                    className="btn-secondary text-sm"
                    onClick={handlePhotoClick}
                  >
                    Change Photo
                  </button>
                  <input
                    type="file"
                    accept="image/*"
                    ref={fileInputRef}
                    className="hidden"
                    onChange={handleFileChange}
                  />
                  <p className="text-xs text-muted-foreground mt-2">JPG, PNG or GIF. Max 2MB.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">First Name</label>
                  <input 
                    type="text" 
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    className="input-trinity" 
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Last Name</label>
                  <input 
                    type="text" 
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className="input-trinity" 
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <label className="text-sm font-medium">Email Address</label>
                  <input 
                    type="email" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-trinity" 
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <label className="text-sm font-medium">Bio</label>
                  <textarea 
                    rows={3}
                    placeholder="Tell us about yourself..."
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    className="input-trinity resize-none"
                  />
                </div>
              </div>

              {(error || success) && (
                <div className="md:col-span-2 text-sm">
                  {error && <p className="text-red-500">{error}</p>}
                  {success && <p className="text-green-600">{success}</p>}
                </div>
              )}

              <div className="flex justify-end pt-4 border-t border-border">
                <button className="btn-primary" type="submit" disabled={isSaving}>
                  <Save className="w-4 h-4" />
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6">
              <div className="card-trinity p-6">
                <h2 className="font-heading text-lg font-semibold mb-1">Change Password</h2>
                <p className="text-sm text-muted-foreground mb-6">Update your password to keep your account secure</p>
                
                <div className="space-y-4 max-w-md">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Current Password</label>
                    <input type="password" className="input-trinity" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">New Password</label>
                    <input type="password" className="input-trinity" />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Confirm New Password</label>
                    <input type="password" className="input-trinity" />
                  </div>
                </div>

                <div className="flex justify-end pt-6 border-t border-border mt-6">
                  <button className="btn-primary">Update Password</button>
                </div>
              </div>

              <div className="card-trinity p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-heading text-lg font-semibold mb-1">Two-Factor Authentication</h2>
                    <p className="text-sm text-muted-foreground">Add an extra layer of security to your account</p>
                  </div>
                  <button className="btn-secondary">Enable 2FA</button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="card-trinity p-6">
              <h2 className="font-heading text-lg font-semibold mb-1">Notification Preferences</h2>
              <p className="text-sm text-muted-foreground mb-6">Choose how you want to be notified</p>

              <div className="space-y-4">
                {[
                  { label: 'Email notifications', description: 'Receive updates via email' },
                  { label: 'Task reminders', description: 'Get reminded about upcoming tasks' },
                  { label: 'Client activity', description: 'Notifications when clients complete actions' },
                  { label: 'AI tool completions', description: 'Know when AI generates documents' },
                  { label: 'Weekly digest', description: 'Summary of your weekly activity' },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-3 border-b border-border last:border-0">
                    <div>
                      <p className="font-medium">{item.label}</p>
                      <p className="text-sm text-muted-foreground">{item.description}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked={i < 3} className="sr-only peer" />
                      <div className="w-11 h-6 bg-muted rounded-full peer peer-checked:bg-accent peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'appearance' && (
            <div className="card-trinity p-6">
              <h2 className="font-heading text-lg font-semibold mb-1">Appearance</h2>
              <p className="text-sm text-muted-foreground mb-6">Customize how Trinity looks</p>

              <div className="space-y-6">
                <div>
                  <label className="text-sm font-medium mb-3 block">Theme</label>
                  <div className="flex gap-3">
                    {['Light', 'Dark', 'System'].map((theme) => (
                      <button
                        key={theme}
                        className={cn(
                          "px-6 py-3 rounded-lg border transition-colors",
                          theme === 'Light' 
                            ? "border-accent bg-accent/5 text-accent" 
                            : "border-border hover:border-accent/50"
                        )}
                      >
                        {theme}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium mb-3 block">Sidebar</label>
                  <div className="flex gap-3">
                    {['Expanded', 'Collapsed'].map((mode) => (
                      <button
                        key={mode}
                        className={cn(
                          "px-6 py-3 rounded-lg border transition-colors",
                          mode === 'Expanded' 
                            ? "border-accent bg-accent/5 text-accent" 
                            : "border-border hover:border-accent/50"
                        )}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
