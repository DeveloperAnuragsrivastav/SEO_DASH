import React from 'react';

interface LoadingSpinnerProps {
  label?: string;
  fullscreen?: boolean;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ 
  label = 'Loading...', 
  fullscreen = false 
}) => {
  return (
    <div className={fullscreen ? 'loader-fullscreen' : 'loader-inline'}>
      <div className="loader-content">
        {/* Animated rings */}
        <div className="loader-rings">
          <div className="loader-ring loader-ring-1" />
          <div className="loader-ring loader-ring-2" />
          <div className="loader-ring loader-ring-3" />
          {/* Center pulse dot */}
          <div className="loader-dot" />
        </div>
        {/* Animated label */}
        <p className="loader-label">{label}</p>
        {/* Progress bar shimmer */}
        <div className="loader-track">
          <div className="loader-track-fill" />
        </div>
      </div>
    </div>
  );
};

export default LoadingSpinner;
