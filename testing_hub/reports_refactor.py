def _aggregate_metrics(snapshots, section):
    if not snapshots:
        return {}
        
    count = len(snapshots)
    
    sum_keys = {
        "gsc": ["clicks", "impressions"],
        "ga4": ["sessions", "users", "organic_sessions", "conversions", "ecommerce_events", "revenue"],
        "gbp": ["views", "searches", "interactions", "calls", "directions", "website_clicks"]
    }.get(section, [])
    
    avg_keys = {
        "gsc": ["ctr", "position"],
        "ga4": ["bounce_rate", "session_duration"],
        "gbp": []
    }.get(section, [])
    
    list_keys = {
        "gsc": ["top_pages"],
        "ga4": ["traffic_sources", "devices", "top_pages", "countries"],
        "gbp": []
    }.get(section, [])
    
    list_merge_key = {
        "top_pages": "page",
        "traffic_sources": "source",
        "devices": "device",
        "countries": "country"
    }
    
    list_sum_keys = {
        "top_pages": ["clicks", "impressions", "sessions", "users", "conversions"],
        "traffic_sources": ["sessions", "users", "conversions"],
        "devices": ["sessions", "users", "conversions"],
        "countries": ["sessions", "users", "conversions"]
    }
    
    result = {}
    
    for k in sum_keys + avg_keys:
        result[k] = 0
        
    for s in snapshots:
        data = s.snapshot.get(section, {}) if s.snapshot else {}
        for k in sum_keys:
            val = data.get(k)
            if val is not None:
                result[k] += val
        for k in avg_keys:
            val = data.get(k)
            if val is not None:
                result[k] += val
            
    if count > 0:
        for k in avg_keys:
            result[k] = result[k] / count
            
    for k in list_keys:
        merged_list = {}
        for s in snapshots:
            data = s.snapshot.get(section, {}) if s.snapshot else {}
            items = data.get(k, [])
            for item in items:
                m_key_name = list_merge_key.get(k)
                m_key = item.get(m_key_name)
                if not m_key:
                    continue
                if m_key not in merged_list:
                    merged_list[m_key] = dict(item)
                else:
                    for sk in list_sum_keys.get(k, []):
                        if sk in item:
                            merged_list[m_key][sk] = merged_list[m_key].get(sk, 0) + item.get(sk, 0)
                            
        for m_key, m_item in merged_list.items():
            if "bounce_rate" in m_item:
                m_item["bounce_rate"] = m_item["bounce_rate"] / count if count > 0 else 0
                
        if list_sum_keys.get(k):
            sort_key = list_sum_keys[k][0]
            result[k] = sorted(merged_list.values(), key=lambda x: x.get(sort_key, 0), reverse=True)
        else:
            result[k] = list(merged_list.values())
            
    return result
def _build_comparative_report(snapshots):
    if not snapshots:
        return {}
    
    months = []
    for s in snapshots:
        months.append(s.end_date.strftime("%B %Y"))
        
    comparative_data = {
        "months": months,
        "kpi_deltas": {},
        "rankings": {"summary": {}, "keywords": []},
        "links": [],
        "ai_visibility": [],
        "activities": [],
        "screenshots": []
    }
    
    latest_snap = snapshots[-1].snapshot if snapshots[-1].snapshot else {}
    comparative_data["kpi_deltas"] = latest_snap.get("kpi_deltas", {})
    comparative_data["narrative"] = latest_snap.get("narrative", "")
    if "rankings" in latest_snap:
        comparative_data["rankings"]["summary"] = latest_snap["rankings"].get("summary", {})
        
    comparative_data["gsc"] = _aggregate_metrics(snapshots, "gsc")
    comparative_data["ga4"] = _aggregate_metrics(snapshots, "ga4")
    comparative_data["gbp"] = _aggregate_metrics(snapshots, "gbp")
        
    kw_map = {}
    for idx, s in enumerate(snapshots):
        month = months[idx]
        snap_data = s.snapshot if s.snapshot else {}
        rank_data = snap_data.get("rankings", {}).get("keywords", [])
        for kw in rank_data:
            kid = kw.get("keyword_id")
            if not kid: continue
            if kid not in kw_map:
                kw_map[kid] = {
                    "keyword_id": kid,
                    "term": kw.get("term"),
                    "positions": {},
                    "change": None,
                    "initial_rank": kw.get("initial_rank")
                }
            kw_map[kid]["positions"][month] = kw.get("position")
            
    latest_rankings = latest_snap.get("rankings", {}).get("keywords", [])
    for kw in latest_rankings:
        kid = kw.get("keyword_id")
        if kid in kw_map:
            kw_map[kid]["change"] = kw.get("change")
            kw_map[kid]["_sort_pos"] = kw.get("position") or 9999
            
    kw_list = list(kw_map.values())
    kw_list.sort(key=lambda x: x.get("_sort_pos", 9999))
    comparative_data["rankings"]["keywords"] = kw_list
    
    for idx, s in enumerate(snapshots):
        month = months[idx]
        snap_data = s.snapshot if s.snapshot else {}
        for item in snap_data.get("links", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["links"].append(item_copy)
        for item in snap_data.get("ai_visibility", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["ai_visibility"].append(item_copy)
        for item in snap_data.get("activities", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["activities"].append(item_copy)
        for item in snap_data.get("screenshots", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["screenshots"].append(item_copy)
            
    ai_vis = comparative_data["ai_visibility"]
    comparative_data["ai_mentioned"] = sum(1 for m in ai_vis if m.get("mentioned"))
    comparative_data["ai_total"] = len(ai_vis)
    comparative_data["ai_platforms"] = len(set(m.get("platform", "") for m in ai_vis))
    
    ai_by_platform = {}
    for m in ai_vis:
        p = m.get("platform", "unknown")
        if p not in ai_by_platform:
            ai_by_platform[p] = {"mentioned": 0, "total": 0}
        ai_by_platform[p]["total"] += 1
        if m.get("mentioned"):
            ai_by_platform[p]["mentioned"] += 1
    comparative_data["ai_by_platform"] = ai_by_platform
    
    links = comparative_data["links"]
    comparative_data["unique_domains"] = len(set(l.get("domain", "") for l in links))
    link_types = {}
    for l in links:
        t = l.get("activity_type", "Other")
        link_types[t] = link_types.get(t, 0) + 1
    comparative_data["link_types"] = link_types
    
    return comparative_data

print("Script built.")
