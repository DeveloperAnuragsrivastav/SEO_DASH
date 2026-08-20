import React from 'react';

export interface RankingRow {
  keyword_id: string;
  term: string;
  current_position: number;
  previous_position?: number;
  best_position?: number;
  change?: number;
  history?: any[];
  group_tag?: string | null;
  source?: string;
  screenshot?: string;
  keyword?: string;
  position?: number;
  tags?: string[];
  ranking_url?: string;
}

const RankingsTable: React.FC<{ data?: RankingRow[] }> = ({ data: _data }) => {
  return <div>Rankings Table</div>;
};

export default RankingsTable;
