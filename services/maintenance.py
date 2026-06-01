from services.integrations import manager

def get_unused_images():
    """
    Cross-references all images against all containers (running/stopped)
    to identify truly unused images across all configured endpoints.
    """
    endpoints = manager.get_all_endpoints()

    unused_list = []

    for ep in endpoints:
        eid = ep.get('Id')
        ename = ep.get('Name')
        p_name = ep.get('_provider')
        provider = manager.get_provider(p_name)
        
        # 1. Get every container (all=1 ensures we don't prune images of stopped containers)
        containers = provider.list_containers(eid)
        if isinstance(containers, dict) and "error" in containers:
            continue
            
        used_image_ids = {c.get('ImageID') for c in containers if c.get('ImageID')}

        # 2. Get every image
        all_images = provider.get_images(eid)
        if isinstance(all_images, dict) and "error" in all_images:
            continue

        # 3. Filter for images whose ID is not in the used set
        for img in all_images:
            img_id = img.get('Id')
            if img_id not in used_image_ids:
                unused_list.append({
                    "endpoint": ename,
                    "endpoint_id": eid,
                    "_provider": p_name,
                    "id": img_id,
                    "tags": img.get('RepoTags') or ["<none>:<none>"],
                    "size": img.get('Size', 0)
                })
                
    return unused_list

def execute_maintenance_prune():
    """Executes a prune on all endpoints where unused images were found."""
    unused = get_unused_images()
    # Group results by provider and endpoint_id
    targets = set()
    for item in unused:
        targets.add((item.get('_provider'), item['endpoint_id']))
    
    results = {}
    for p_name, eid in targets:
        provider = manager.get_provider(p_name)
        if provider:
            results[eid] = provider.prune_images(eid, prune_all=True)
    return results