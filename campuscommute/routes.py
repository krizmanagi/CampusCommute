"""Fictional route catalogue. Route IDs are the keys used in observations and CSV files."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    id: str
    name: str
    stops: tuple
    base_demand: float  # synthetic-data scale factor only


ROUTES = (
    Route("campus-loop", "Campus Loop",
          ("Student Union", "Main Library", "Science Quad", "Arts Center", "Rec Center"), 1.6),
    Route("north-residence", "North Residence Express",
          ("North Halls", "Maple Commons", "Student Union", "Engineering"), 1.3),
    Route("south-residence", "South Residence Express",
          ("South Towers", "Birch Village", "Main Library", "Business School"), 1.2),
    Route("medical-center", "Medical Center Connector",
          ("Student Union", "Health Sciences", "University Hospital", "Research Park"), 1.0),
    Route("downtown", "Downtown Link",
          ("Main Gate", "Transit Center", "City Hall", "Riverfront Market"), 1.1),
    Route("research-park", "Research Park Shuttle",
          ("Engineering", "Innovation Hub", "Research Park", "East Labs"), 0.7),
    Route("athletics", "Athletics Shuttle",
          ("Rec Center", "Stadium", "Aquatics Center", "West Fields"), 0.6),
    Route("west-lots", "West Parking Lots",
          ("Lot W1", "Lot W2", "Arts Center", "Student Union"), 0.9),
    Route("east-lots", "East Parking Lots",
          ("Lot E1", "Lot E3", "Business School", "Main Library"), 0.85),
    Route("graduate-village", "Graduate Village",
          ("Graduate Village", "Law School", "Main Library", "Health Sciences"), 0.75),
    Route("train-station", "Train Station Express",
          ("Main Gate", "Central Station", "Bus Terminal"), 0.95),
    Route("night-owl", "Night Owl",
          ("Student Union", "North Halls", "South Towers", "Graduate Village"), 0.5),
    Route("airport", "Airport Express",
          ("Student Union", "Transit Center", "Regional Airport"), 0.4),
)

ROUTES_BY_ID = {route.id: route for route in ROUTES}

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
