import { useState } from 'react';
import { Search, Brain, FileText, Users, Target, Calendar, Shield, TrendingUp, Briefcase, ClipboardList, ArrowRight, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

const aiTools = [
  { 
    id: 'business-plan', 
    name: 'Business Plan Generator', 
    description: 'Generate comprehensive business plans with financial projections and market analysis',
    icon: Briefcase,
    category: 'Strategy',
    popular: true
  },
  { 
    id: 'position-description', 
    name: 'Position Description Generator', 
    description: 'Create detailed job descriptions with KPIs, capabilities, and reporting lines',
    icon: Users,
    category: 'HR',
    popular: true
  },
  { 
    id: 'org-redesign', 
    name: 'Organisation Redesign Tool', 
    description: 'Map and optimize organizational structures for improved efficiency',
    icon: Target,
    category: 'Operations',
    popular: false
  },
  { 
    id: 'operating-rhythm', 
    name: 'Operating Rhythm Planner', 
    description: 'Design meeting cadences and operational rhythms for your business',
    icon: Calendar,
    category: 'Operations',
    popular: true
  },
  { 
    id: 'kpi-builder', 
    name: 'KPI Builder', 
    description: 'Create KPI trees and dashboard briefs aligned with business objectives',
    icon: TrendingUp,
    category: 'Strategy',
    popular: false
  },
  { 
    id: 'policy-generator', 
    name: 'Policy Generator', 
    description: 'Generate AI Use, Privacy, and Data Handling policies compliant with regulations',
    icon: Shield,
    category: 'Compliance',
    popular: false
  },
  { 
    id: 'risk-register', 
    name: 'Risk Register Builder', 
    description: 'Identify and categorize business risks with mitigation strategies',
    icon: ClipboardList,
    category: 'Risk',
    popular: false
  },
  { 
    id: 'diagnostic-report', 
    name: 'Diagnostic Report Generator', 
    description: 'Transform diagnostic data into actionable insights and recommendations',
    icon: FileText,
    category: 'Analysis',
    popular: true
  },
];

const categories = ['All', ...new Set(aiTools.map(t => t.category))];

export default function AIToolsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('All');

  const filteredTools = aiTools.filter(tool => {
    const matchesSearch = tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tool.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = categoryFilter === 'All' || tool.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">AI Tools</h1>
          <p className="text-muted-foreground mt-1">Generate business artefacts with AI assistance</p>
        </div>
      </div>

      {/* Hero Section */}
      <div className="card-trinity p-8 relative overflow-hidden" style={{ background: 'var(--gradient-hero)' }}>
        <div className="absolute top-0 right-0 w-64 h-64 bg-accent/10 rounded-full blur-3xl" />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center">
              <Brain className="w-6 h-6 text-accent-foreground" />
            </div>
            <div>
              <h2 className="font-heading text-xl font-bold text-primary-foreground">Trinity AI Orchestrator</h2>
              <p className="text-primary-foreground/70 text-sm">30+ AI tools for business advisory</p>
            </div>
          </div>
          <p className="text-primary-foreground/80 max-w-xl mb-6">
            Access our suite of AI-powered tools designed specifically for business advisors. 
            Generate professional documents, analyze data, and create strategic plans in minutes.
          </p>
          <div className="flex flex-wrap gap-3">
            <span className="px-3 py-1.5 rounded-full bg-accent/20 text-accent text-sm font-medium">GPT-4 Powered</span>
            <span className="px-3 py-1.5 rounded-full bg-accent/20 text-accent text-sm font-medium">Template-Based</span>
            <span className="px-3 py-1.5 rounded-full bg-accent/20 text-accent text-sm font-medium">Schema Validated</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search tools..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-trinity pl-10 w-full"
          />
        </div>
        <div className="flex items-center gap-2 overflow-x-auto pb-2 sm:pb-0">
          {categories.map((category) => (
            <button
              key={category}
              onClick={() => setCategoryFilter(category)}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all",
                categoryFilter === category 
                  ? "bg-accent text-accent-foreground" 
                  : "bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              {category}
            </button>
          ))}
        </div>
      </div>

      {/* Tools Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredTools.map((tool) => (
          <div 
            key={tool.id}
            className="card-trinity p-6 cursor-pointer group hover:shadow-trinity-lg"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="w-12 h-12 rounded-xl bg-accent/10 flex items-center justify-center group-hover:bg-accent/20 transition-colors">
                <tool.icon className="w-6 h-6 text-accent" />
              </div>
              {tool.popular && (
                <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-warning/10 text-warning text-xs font-medium">
                  <Sparkles className="w-3 h-3" />
                  Popular
                </span>
              )}
            </div>
            
            <h3 className="font-heading font-semibold text-foreground mb-2 group-hover:text-accent transition-colors">
              {tool.name}
            </h3>
            <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
              {tool.description}
            </p>
            
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
                {tool.category}
              </span>
              <button className="flex items-center gap-1 text-sm font-medium text-accent opacity-0 group-hover:opacity-100 transition-opacity">
                Launch <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredTools.length === 0 && (
        <div className="text-center py-12">
          <Brain className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">No AI tools found matching your search</p>
        </div>
      )}
    </div>
  );
}
