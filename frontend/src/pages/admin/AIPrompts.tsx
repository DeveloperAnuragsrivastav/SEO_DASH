import { Navigate, useParams } from 'react-router-dom';

/** Prompts are rows of the AI Visibility sheet now; this old address leads there. */
export default function AIPrompts() {
  const { clientId } = useParams();
  return <Navigate to={`/clients/${clientId}/ai-mentions-data`} replace />;
}
