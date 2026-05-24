"""Repository modules — data access helpers for each entity.

Routes call into these; repositories own queries and ownership/role checks
where ambient. Anything that needs cross-entity reasoning lives in a
service module (none yet — small enough that routes orchestrate directly).
"""
