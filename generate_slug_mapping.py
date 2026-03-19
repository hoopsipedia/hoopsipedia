#!/usr/bin/env python3
"""
Generate ESPN ID to Sports Reference slug mapping from data.json
This creates an initial mapping that can be manually refined.
"""

import json
import re
from pathlib import Path


def generate_slug_from_team_name(team_name: str) -> str:
    """
    Convert a team name to a Sports Reference slug format.
    Examples:
      "Kentucky Wildcats" -> "kentucky"
      "North Carolina Tar Heels" -> "north-carolina"
      "Michigan State Spartans" -> "michigan-state"
      "Texas Christian University Horned Frogs" -> "texas-christian"
    """
    # Remove common suffixes
    name = team_name
    suffixes = ['Wildcats', 'Tar Heels', 'Spartans', 'Hoosiers', 'Boilermakers',
                'Aggies', 'Nittany Lions', 'Badgers', 'Gophers', 'Hawkeyes',
                'Cyclones', 'Jayhawks', 'Sooners', 'Cowboys', 'Eagles',
                'Tigers', 'Lions', 'Bears', 'Bruins', 'Trojans',
                'Ducks', 'Beavers', 'Cougars', 'Huskies', 'Huskies',
                'Buckeyes', 'Scarlet Knights', 'Terrapins', 'Mountaineers',
                'Longhorns', 'Utes', 'Aztecs', 'Demons', 'Gamecocks',
                'Volunteers', 'Vandy', 'Razorbacks', 'Bengals', 'Hokies',
                'Hokies', 'Demon Deacons', 'Blue Devils', 'Yellow Jackets',
                'Ramblers', 'Red Storm', 'Crimson', 'Crimson Tide', 'Cardinals',
                'Hoosiers', 'Boilermakers', 'Golden Eagles', 'Hurricanes',
                'Knights', 'Bearcats', 'Owls', 'Musketeers', 'Friars',
                'Bulldogs', 'Wildcats', 'Fighting Illini', 'Cornhuskers',
                'Orangemen', 'Toreros', 'Shockers', 'Rams', 'Cowboys',
                'Panthers', 'Leopards', 'Antelopes', 'Greyhounds', 'Trojans',
                'Spartans', 'Jaguars', 'Blazers']

    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
            break

    # Handle special multi-word school names
    # Convert to lowercase and replace spaces with hyphens
    slug = name.lower().strip()
    slug = re.sub(r'[&\']', '', slug)  # Remove & and apostrophes
    slug = re.sub(r'\s+', '-', slug)    # Replace spaces with hyphens
    slug = re.sub(r'-+', '-', slug)     # Collapse multiple hyphens
    slug = slug.strip('-')              # Remove leading/trailing hyphens

    # Handle special cases
    special_cases = {
        'california': 'california-berkeley',
        'southern-california': 'southern-california',
        'penn-state': 'penn-state',
        'texas-christian': 'texas-christian',
        'brigham-young': 'brigham-young',
        'miami': 'miami-florida',
        'florida-international': 'florida-international',
        'florida-atlantic': 'florida-atlantic',
        'louisiana': 'louisiana-monroe',
        'texarkana': 'arkansas-texarkana',
    }

    if slug in special_cases:
        return special_cases[slug]

    return slug


def main():
    """Generate slug mapping from data.json."""
    data_file = Path(__file__).parent / 'data.json'

    if not data_file.exists():
        print(f"ERROR: {data_file} not found")
        return

    print(f"Reading team data from {data_file}...")
    with open(data_file) as f:
        data = json.load(f)

    teams_dict = data.get('H', {})
    print(f"Found {len(teams_dict)} teams\n")

    slug_mapping = {}
    conflicts = {}

    for espn_id, team_data in teams_dict.items():
        if isinstance(team_data, list) and len(team_data) > 0:
            team_name = team_data[0]
        else:
            team_name = str(team_data)

        slug = generate_slug_from_team_name(team_name)

        # Track potential conflicts
        if slug in slug_mapping.values():
            if slug not in conflicts:
                conflicts[slug] = []
            conflicts[slug].append((espn_id, team_name))
        else:
            slug_mapping[espn_id] = slug

    # Print generated mapping
    print("Generated slug mapping:")
    for espn_id in sorted(slug_mapping.keys(), key=lambda x: int(x)):
        team_name = teams_dict[espn_id][0] if isinstance(teams_dict[espn_id], list) else teams_dict[espn_id]
        slug = slug_mapping[espn_id]
        print(f"  {espn_id}: {slug:30} ({team_name})")

    # Save to file
    output_file = Path(__file__).parent / 'slug_mapping.json'
    with open(output_file, 'w') as f:
        json.dump(slug_mapping, f, indent=2, sort_keys=True)

    print(f"\n✓ Slug mapping saved to {output_file}")
    print(f"  Total mappings: {len(slug_mapping)}")

    if conflicts:
        print(f"\n⚠ Note: {len(conflicts)} potential slug conflicts detected:")
        for slug, teams in conflicts.items():
            print(f"  {slug}:")
            for espn_id, team_name in teams:
                print(f"    - {espn_id}: {team_name}")


if __name__ == '__main__':
    main()
