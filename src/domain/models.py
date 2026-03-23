from dataclasses import dataclass


@dataclass
class Transaction:
    date: str              # ISO format: 2025-02-02
    time: str              # HH:MM
    asset_name: str        # Ex: "Core S&P 500 USD (Acc)"
    asset_price: float     # Prix unitaire de l'actif
    units: float           # Nombre d'unites
    fees: float            # Frais (0.0 si "Free")
    total: float           # Montant total
    type: str              # "buy", "sell" ou "pea"
    status: str            # "completed", "executed", "rejected", etc.
    source_file: str       # Nom du fichier source
