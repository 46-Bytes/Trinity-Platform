import { useState } from 'react';
import { Search, Plus, Upload, FileText, File, FileSpreadsheet, Presentation, Folder, MoreHorizontal, Download, Trash2, Eye } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const mockDocuments = [
  { id: '1', name: 'Business Plan - Acme Corp v2.pdf', type: 'pdf', size: '2.4 MB', client: 'Acme Corp', uploadedBy: 'Emma Thompson', date: 'Dec 1, 2024', source: 'ai' },
  { id: '2', name: 'Financial Analysis Q4.xlsx', type: 'excel', size: '1.1 MB', client: 'TechStart', uploadedBy: 'James Wilson', date: 'Nov 28, 2024', source: 'upload' },
  { id: '3', name: 'Strategy Presentation.pptx', type: 'powerpoint', size: '5.2 MB', client: 'Global Solutions', uploadedBy: 'Lisa Anderson', date: 'Nov 25, 2024', source: 'ai' },
  { id: '4', name: 'Diagnostic Report.pdf', type: 'pdf', size: '890 KB', client: 'Innovate Ltd', uploadedBy: 'System', date: 'Nov 22, 2024', source: 'ai' },
  { id: '5', name: 'Position Descriptions.docx', type: 'word', size: '345 KB', client: 'Acme Corp', uploadedBy: 'Emma Thompson', date: 'Nov 20, 2024', source: 'ai' },
  { id: '6', name: 'Annual Report 2023.pdf', type: 'pdf', size: '8.5 MB', client: 'Pacific Traders', uploadedBy: 'David Chen', date: 'Nov 18, 2024', source: 'upload' },
];

const fileIcons: Record<string, typeof FileText> = {
  pdf: FileText,
  excel: FileSpreadsheet,
  powerpoint: Presentation,
  word: File,
};

const fileColors: Record<string, string> = {
  pdf: 'text-red-500 bg-red-50',
  excel: 'text-green-600 bg-green-50',
  powerpoint: 'text-orange-500 bg-orange-50',
  word: 'text-blue-500 bg-blue-50',
};

export default function DocumentsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const filteredDocuments = mockDocuments.filter(doc => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.client.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === 'all' || doc.type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Documents</h1>
          <p className="text-muted-foreground mt-1">Manage and access all your documents</p>
        </div>
        <button className="btn-primary">
          <Upload className="w-4 h-4" />
          Upload Document
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">Total Documents</p>
          <p className="text-2xl font-heading font-bold mt-1">{mockDocuments.length}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">AI Generated</p>
          <p className="text-2xl font-heading font-bold mt-1">{mockDocuments.filter(d => d.source === 'ai').length}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">Uploaded</p>
          <p className="text-2xl font-heading font-bold mt-1">{mockDocuments.filter(d => d.source === 'upload').length}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm text-muted-foreground">Total Size</p>
          <p className="text-2xl font-heading font-bold mt-1">18.4 MB</p>
        </div>
      </div>

      <div className="card-trinity p-6">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-trinity pl-10 w-full"
            />
          </div>
          <select 
            className="input-trinity w-full sm:w-40"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All Types</option>
            <option value="pdf">PDF</option>
            <option value="excel">Excel</option>
            <option value="powerpoint">PowerPoint</option>
            <option value="word">Word</option>
          </select>
          <div className="flex items-center gap-1 p-1 bg-muted rounded-lg">
            <button 
              onClick={() => setViewMode('grid')}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm transition-colors",
                viewMode === 'grid' ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              Grid
            </button>
            <button 
              onClick={() => setViewMode('list')}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm transition-colors",
                viewMode === 'list' ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              List
            </button>
          </div>
        </div>

        {viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredDocuments.map((doc) => {
              const Icon = fileIcons[doc.type] || FileText;
              return (
                <div 
                  key={doc.id}
                  className="p-4 rounded-xl border border-border hover:border-accent/50 hover:shadow-trinity-md transition-all cursor-pointer group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", fileColors[doc.type])}>
                      <Icon className="w-6 h-6" />
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="p-1.5 rounded-lg hover:bg-muted transition-colors opacity-0 group-hover:opacity-100">
                          <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem className="cursor-pointer">
                          <Eye className="w-4 h-4 mr-2" />
                          View
                        </DropdownMenuItem>
                        <DropdownMenuItem className="cursor-pointer">
                          <Download className="w-4 h-4 mr-2" />
                          Download
                        </DropdownMenuItem>
                        <DropdownMenuItem className="cursor-pointer text-destructive">
                          <Trash2 className="w-4 h-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  
                  <h4 className="font-medium text-sm truncate mb-1 group-hover:text-accent transition-colors">{doc.name}</h4>
                  <p className="text-xs text-muted-foreground mb-3">{doc.client}</p>
                  
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{doc.size}</span>
                    <span>{doc.date}</span>
                  </div>
                  
                  {doc.source === 'ai' && (
                    <span className="mt-2 inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-accent/10 text-accent">
                      AI Generated
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-trinity">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Client</th>
                  <th>Size</th>
                  <th>Uploaded By</th>
                  <th>Date</th>
                  <th className="w-12"></th>
                </tr>
              </thead>
              <tbody>
                {filteredDocuments.map((doc) => {
                  const Icon = fileIcons[doc.type] || FileText;
                  return (
                    <tr key={doc.id} className="cursor-pointer">
                      <td>
                        <div className="flex items-center gap-3">
                          <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0", fileColors[doc.type])}>
                            <Icon className="w-4 h-4" />
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium truncate max-w-[200px]">{doc.name}</span>
                            {doc.source === 'ai' && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-accent/10 text-accent flex-shrink-0">AI</span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="text-muted-foreground">{doc.client}</td>
                      <td className="text-muted-foreground">{doc.size}</td>
                      <td className="text-muted-foreground">{doc.uploadedBy}</td>
                      <td className="text-muted-foreground">{doc.date}</td>
                      <td>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button className="p-2 rounded-lg hover:bg-muted transition-colors">
                              <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem className="cursor-pointer">
                              <Download className="w-4 h-4 mr-2" />
                              Download
                            </DropdownMenuItem>
                            <DropdownMenuItem className="cursor-pointer text-destructive">
                              <Trash2 className="w-4 h-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
