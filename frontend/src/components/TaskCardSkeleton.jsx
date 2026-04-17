import React from 'react';
import { Card } from './ui/card';

const TaskCardSkeleton = () => {
  return (
    <Card className="p-3">
      <div className="animate-pulse">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1">
            <div className="h-4 bg-slate-200 rounded w-3/4 mb-1"></div>
            <div className="h-3 bg-slate-100 rounded w-1/2"></div>
          </div>
          <div className="h-5 bg-slate-200 rounded w-16 mr-2"></div>
        </div>
        <div className="flex items-center gap-3">
          <div className="h-4 bg-slate-100 rounded w-16"></div>
          <div className="h-4 bg-slate-100 rounded w-12"></div>
        </div>
      </div>
    </Card>
  );
};

export default TaskCardSkeleton;
