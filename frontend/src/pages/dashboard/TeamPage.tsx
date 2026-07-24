import { useEffect, useState } from 'react';
import { Loader2, Mail, Trash2, UserPlus, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import {
  ACCESS_LEVEL_DESCRIPTIONS,
  ACCESS_LEVEL_LABELS,
  getTeam,
  inviteTeamMember,
  revokeTeamMember,
  updateTeamMember,
  type Seats,
  type TeamAccessLevel,
  type TeamMember,
} from '@/lib/selfServiceApi';

const ACCESS_LEVELS: TeamAccessLevel[] = ['viewer', 'collaborator'];

const STATUS_STYLES: Record<string, string> = {
  invited: 'bg-amber-100 text-amber-700',
  active: 'bg-emerald-100 text-emerald-700',
  revoked: 'bg-muted text-muted-foreground',
};

/**
 * Team management for self-service business owners (Feature 7).
 *
 * Owners invite team members to collaborate on their program. The seat cap
 * comes from their plan; the access level controls what a member can do.
 */
export default function TeamPage() {
  const { toast } = useToast();

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [seats, setSeats] = useState<Seats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteAccess, setInviteAccess] = useState<TeamAccessLevel>('viewer');
  const [inviting, setInviting] = useState(false);

  const loadTeam = async () => {
    try {
      const data = await getTeam();
      setMembers(data.members);
      setSeats(data.seats);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your team.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTeam();
  }, []);

  const seatsFull = !!seats && seats.team_members_used >= seats.team_member_limit;

  const handleInvite = async (event: React.FormEvent) => {
    event.preventDefault();
    setInviting(true);
    try {
      await inviteTeamMember({
        email: inviteEmail.trim(),
        name: inviteName.trim() || undefined,
        access_level: inviteAccess,
      });
      toast({
        title: 'Invitation sent',
        description: `${inviteEmail} will receive an email to set their password.`,
      });
      setInviteOpen(false);
      setInviteEmail('');
      setInviteName('');
      setInviteAccess('viewer');
      await loadTeam();
    } catch (err) {
      toast({
        title: 'Could not send the invitation',
        description: err instanceof Error ? err.message : 'Please try again.',
        variant: 'destructive',
      });
    } finally {
      setInviting(false);
    }
  };

  const handleAccessChange = async (member: TeamMember, level: TeamAccessLevel) => {
    try {
      await updateTeamMember(member.id, level);
      toast({ title: 'Access updated', description: `${member.email} is now a ${ACCESS_LEVEL_LABELS[level].toLowerCase()}.` });
      await loadTeam();
    } catch (err) {
      toast({
        title: 'Could not update access',
        description: err instanceof Error ? err.message : 'Please try again.',
        variant: 'destructive',
      });
    }
  };

  const handleRevoke = async (member: TeamMember) => {
    try {
      await revokeTeamMember(member.id);
      toast({ title: 'Team member removed', description: `${member.email} no longer has access.` });
      await loadTeam();
    } catch (err) {
      toast({
        title: 'Could not remove the team member',
        description: err instanceof Error ? err.message : 'Please try again.',
        variant: 'destructive',
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card-trinity p-6">
        <div className="text-center py-12">
          <p className="text-destructive mb-2">Could not load your team</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Team</h1>
          <p className="text-muted-foreground mt-1">
            Invite people from your business to collaborate on your program.
          </p>
        </div>
        <Button
          onClick={() => setInviteOpen(true)}
          className="btn-primary"
          disabled={seatsFull}
          title={seatsFull ? 'All team member seats on your plan are in use' : undefined}
        >
          <UserPlus className="w-4 h-4 mr-2" />
          Invite team member
        </Button>
      </div>

      {seats && (
        <div className="card-trinity p-4 flex items-center gap-3">
          <Users className="w-5 h-5 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Using <span className="font-medium text-foreground">{seats.team_members_used}</span> of{' '}
            <span className="font-medium text-foreground">{seats.team_member_limit}</span> team
            member seats on your plan.
          </p>
        </div>
      )}

      <div className="card-trinity">
        {members.length === 0 ? (
          <div className="text-center py-16 px-6">
            <Users className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-medium text-foreground mb-1">No team members yet</p>
            <p className="text-sm text-muted-foreground">
              Invite a colleague to help you work through your program.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {members.map((member) => (
              <div key={member.id} className="p-4 flex items-center gap-4 flex-wrap">
                <div className="flex-1 min-w-[200px]">
                  <p className="font-medium text-foreground">{member.name || member.email}</p>
                  <p className="text-sm text-muted-foreground flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5" />
                    {member.email}
                  </p>
                </div>

                <Badge className={STATUS_STYLES[member.status] ?? STATUS_STYLES.revoked}>
                  {member.status === 'invited' ? 'Invitation sent' : member.status}
                </Badge>

                <Select
                  value={member.access_level}
                  onValueChange={(value) => handleAccessChange(member, value as TeamAccessLevel)}
                >
                  <SelectTrigger className="w-[150px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ACCESS_LEVELS.map((level) => (
                      <SelectItem key={level} value={level}>
                        {ACCESS_LEVEL_LABELS[level]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleRevoke(member)}
                  aria-label={`Remove ${member.email}`}
                >
                  <Trash2 className="w-4 h-4 text-destructive" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <form onSubmit={handleInvite}>
            <DialogHeader>
              <DialogTitle>Invite a team member</DialogTitle>
              <DialogDescription>
                They'll receive an email to set their password and join your workspace.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="inviteEmail">Email</Label>
                <Input
                  id="inviteEmail"
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="colleague@yourbusiness.com.au"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="inviteName">Name (optional)</Label>
                <Input
                  id="inviteName"
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="Alex Taylor"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="inviteAccess">Access level</Label>
                <Select
                  value={inviteAccess}
                  onValueChange={(value) => setInviteAccess(value as TeamAccessLevel)}
                >
                  <SelectTrigger id="inviteAccess">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ACCESS_LEVELS.map((level) => (
                      <SelectItem key={level} value={level}>
                        {ACCESS_LEVEL_LABELS[level]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-sm text-muted-foreground">
                  {ACCESS_LEVEL_DESCRIPTIONS[inviteAccess]}
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setInviteOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" className="btn-primary" disabled={inviting}>
                {inviting ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Sending...
                  </span>
                ) : (
                  'Send invitation'
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
