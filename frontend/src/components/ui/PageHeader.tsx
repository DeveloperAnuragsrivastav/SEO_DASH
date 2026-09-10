import React from 'react';
import { Link } from 'react-router-dom';

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface PageHeaderProps {
  title: string;
  /** Small status chip rendered beside the title, e.g. "Active Client". */
  badge?: React.ReactNode;
  subtitle?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, badge, subtitle, breadcrumbs, actions }) => {
  // const { clientId } = useParams();

  // Auto-generate breadcrumbs if not provided
  const crumbs = breadcrumbs || [{ label: 'Home', href: '/admin/clients' }];

  return (
    <div className="page-header">
      {crumbs.length > 0 && (
        <nav className="page-breadcrumb">
          {crumbs.map((crumb, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="breadcrumb-sep">/</span>}
              {crumb.href ? (
                <Link to={crumb.href} className="breadcrumb-link">{crumb.label}</Link>
              ) : (
                <span className="breadcrumb-current">{crumb.label}</span>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}
      <div className="page-header-row">
        <div className="page-header-text">
          <h1 className="page-title">
            {title}
            {badge}
          </h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="page-header-actions">{actions}</div>}
      </div>
    </div>
  );
};

export default PageHeader;
