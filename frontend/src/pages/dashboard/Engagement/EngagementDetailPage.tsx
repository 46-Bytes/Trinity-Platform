import { useParams } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToolSurvey } from '@/components/engagement/tools/ToolSurvey';
import { EngagementChatbot } from '@/components/engagement/chatbot';
import { GeneratedFilesList } from '@/components/engagement/overview';
import type { GeneratedFileProps } from '@/components/engagement/overview';

export default function EngagementDetailPage() {
  const { engagementId } = useParams<{ engagementId: string }>();

  if (!engagementId) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Engagement not found</p>
      </div>
    );
  }

  // Dummy generated files data - Replace with actual data from Redux/API
  const dummyFiles: GeneratedFileProps[] = [
    {
      id: '1',
      name: 'Business Health Diagnostic Report',
      type: 'pdf',
      generatedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000), // 2 days ago
      generatedBy: 'Trinity AI',
      size: '2.4 MB',
      toolType: 'diagnostic',
    },
    {
      id: '2',
      name: 'Q4 2024 Business Plan',
      type: 'docx',
      generatedAt: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000), // 5 days ago
      generatedBy: 'John Doe',
      size: '1.8 MB',
      toolType: 'business-plan',
    },
    {
      id: '3',
      name: 'Financial Analysis Dashboard',
      type: 'xlsx',
      generatedAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), // 7 days ago
      generatedBy: 'Trinity AI',
      size: '856 KB',
      toolType: 'kpi-builder',
    },
    {
      id: '4',
      name: 'Organizational Structure Presentation',
      type: 'pptx',
      generatedAt: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000), // 10 days ago
      generatedBy: 'Jane Smith',
      size: '3.2 MB',
      toolType: 'org-redesign',
    },
  ];

  const handleDownload = (fileId: string) => {
    // TODO: Implement download functionality
    console.log('Downloading file:', fileId);
    // You can dispatch a Redux action or call an API here
  };

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Engagement Details</h1>
        <p className="text-muted-foreground mt-1">Manage your client engagement</p>
      </div>
      
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-fit grid-cols-3">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="diagnostic">Diagnostic</TabsTrigger>
          <TabsTrigger value="chatbot">Chat Bot</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <div className="space-y-6">
            {/* Engagement Summary Card */}
            <div className="card-trinity p-6">
              <h2 className="text-xl font-semibold mb-4">Engagement Overview</h2>
              <p className="text-muted-foreground">
                Engagement overview and details will be displayed here.
              </p>
              {/* TODO: Add engagement overview content */}
            </div>

            {/* Generated Files Section */}
            <div className="card-trinity p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Generated Files</h2>
                <span className="text-sm text-muted-foreground">
                  {dummyFiles.length} file{dummyFiles.length !== 1 ? 's' : ''}
                </span>
              </div>
              <GeneratedFilesList files={dummyFiles} onDownload={handleDownload} />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="diagnostic" className="mt-6">
          <div className="card-trinity p-6">
            <ToolSurvey engagementId={engagementId} toolType="diagnostic" />
          </div>
        </TabsContent>

        <TabsContent value="chatbot" className="mt-6">
          <div className="card-trinity p-6">
            <EngagementChatbot engagementId={engagementId} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

