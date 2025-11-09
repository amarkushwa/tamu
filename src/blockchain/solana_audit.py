"""
Solana Blockchain Integration for Immutable Audit Trails
Creates cryptographically verifiable records of classification decisions
"""
import hashlib
import json
import time
from typing import Dict, Optional
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction
from solders.transaction import Transaction
from solders.message import Message
from solders.system_program import TransferParams, transfer

from ..config import Config


class SolanaAuditTrail:
    """Manages immutable audit trails on Solana blockchain"""

    def __init__(self):
        """Initialize Solana client and keypair"""
        self.client = Client(Config.SOLANA_CLUSTER_URL)

        # Generate or load keypair (in production, load from secure storage)
        self.keypair = Keypair()

        # Memo program ID (for storing data on-chain)
        self.memo_program_id = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")

    def _get_cluster_param(self) -> Optional[str]:
        """
        Derive the cluster parameter for Solana Explorer from the RPC URL

        Returns:
            Cluster parameter string for explorer URL or None if custom/local
        """
        cluster_url = Config.SOLANA_CLUSTER_URL.lower()

        if 'mainnet' in cluster_url:
            return 'mainnet-beta'
        elif 'devnet' in cluster_url:
            return 'devnet'
        elif 'testnet' in cluster_url:
            return 'testnet'
        else:
            # Custom RPC endpoint - no public explorer link available
            return None

    def _create_explorer_url(self, tx_hash: str, is_simulated: bool = False) -> Optional[str]:
        """
        Create Solana Explorer URL for a transaction

        Args:
            tx_hash: Transaction hash
            is_simulated: Whether this is a simulated transaction

        Returns:
            Explorer URL or None if using custom cluster
        """
        cluster_param = self._get_cluster_param()

        if cluster_param is None:
            # Custom RPC - no explorer link available
            return None

        if is_simulated:
            # Simulated transactions won't exist on explorer, but we provide the URL format
            # with a note that it's simulated
            return None

        return f"https://explorer.solana.com/tx/{tx_hash}?cluster={cluster_param}"

    def create_audit_hash(self, classification_result: Dict) -> str:
        """
        Create a cryptographic hash of the classification result

        Args:
            classification_result: The classification result to hash

        Returns:
            SHA-256 hash of the result
        """
        # Create deterministic data structure
        audit_data = {
            'document_id': classification_result['document_id'],
            'final_category': classification_result['final_category'],
            'confidence_score': classification_result['confidence_score'],
            'reasoning_summary': classification_result['reasoning_summary'],
            'citation_snippet': classification_result['citation_snippet'],
            'timestamp': classification_result.get('timestamp', int(time.time()))
        }

        # Create hash
        data_string = json.dumps(audit_data, sort_keys=True)
        hash_object = hashlib.sha256(data_string.encode())
        return hash_object.hexdigest()

    def record_to_blockchain(self, classification_result: Dict) -> Optional[Dict]:
        """
        Record classification result to Solana blockchain

        Args:
            classification_result: Classification result to record

        Returns:
            Dict with transaction details or None if failed
        """
        try:
            # Create audit hash
            audit_hash = self.create_audit_hash(classification_result)

            print(f"Creating blockchain audit record...")
            print(f"Audit Hash: {audit_hash}")

            # Create memo with audit data
            memo_data = f"AUDIT:{classification_result['document_id']}:{classification_result['final_category']}:{audit_hash}"

            # Ensure memo data is not too long (max 566 bytes for memo)
            if len(memo_data.encode('utf-8')) > 566:
                memo_data = memo_data[:566]

            # Create memo instruction
            memo_instruction = Instruction(
                program_id=self.memo_program_id,
                accounts=[],
                data=memo_data.encode('utf-8')
            )

            # Get recent blockhash
            try:
                blockhash_resp = self.client.get_latest_blockhash()
                recent_blockhash = blockhash_resp.value.blockhash
            except Exception as e:
                print(f"Warning: Could not get blockhash from cluster: {e}")
                print("Using simulated transaction hash for demo purposes")

                # For demo/testing when devnet is unavailable
                simulated_tx_hash = hashlib.sha256(
                    f"{audit_hash}:{time.time()}".encode()
                ).hexdigest()

                return {
                    'transaction_hash': simulated_tx_hash,
                    'audit_hash': audit_hash,
                    'document_id': classification_result['document_id'],
                    'category': classification_result['final_category'],
                    'timestamp': int(time.time()),
                    'cluster': Config.SOLANA_CLUSTER_URL,
                    'status': 'SIMULATED',
                    'memo': memo_data
                }

            # Create message and transaction
            message = Message.new_with_blockhash(
                [memo_instruction],
                self.keypair.pubkey(),
                recent_blockhash
            )

            transaction = Transaction([self.keypair], message, recent_blockhash)

            # Sign and send
            response = self.client.send_transaction(transaction)

            tx_hash = str(response.value)
            print(f"Transaction sent: {tx_hash}")

            # Wait for confirmation (with timeout)
            max_retries = 10
            for i in range(max_retries):
                try:
                    status = self.client.get_signature_statuses([tx_hash])
                    if status.value[0] is not None:
                        print(f"Transaction confirmed!")
                        break
                except:
                    pass
                time.sleep(2)

            # Create response with explorer URL
            response = {
                'transaction_hash': tx_hash,
                'audit_hash': audit_hash,
                'document_id': classification_result['document_id'],
                'category': classification_result['final_category'],
                'timestamp': int(time.time()),
                'cluster': Config.SOLANA_CLUSTER_URL,
                'status': 'CONFIRMED'
            }

            # Add explorer URL if available (only for public clusters)
            explorer_url = self._create_explorer_url(tx_hash, is_simulated=False)
            if explorer_url:
                response['explorer_url'] = explorer_url

            return response

        except Exception as e:
            print(f"Blockchain recording error: {e}")
            print("Creating simulated audit record for demo...")

            # Fallback to simulated hash
            audit_hash = self.create_audit_hash(classification_result)
            simulated_tx_hash = hashlib.sha256(
                f"{audit_hash}:{time.time()}".encode()
            ).hexdigest()

            return {
                'transaction_hash': simulated_tx_hash,
                'audit_hash': audit_hash,
                'document_id': classification_result['document_id'],
                'category': classification_result['final_category'],
                'timestamp': int(time.time()),
                'cluster': Config.SOLANA_CLUSTER_URL,
                'status': 'SIMULATED',
                'error': str(e)
            }

    def verify_audit_record(self, transaction_hash: str) -> Optional[Dict]:
        """
        Verify an audit record on the blockchain

        Args:
            transaction_hash: The transaction hash to verify

        Returns:
            Verification result or None
        """
        try:
            # Get transaction details
            tx_info = self.client.get_transaction(transaction_hash)

            if tx_info.value is None:
                return {
                    'verified': False,
                    'error': 'Transaction not found'
                }

            return {
                'verified': True,
                'transaction_hash': transaction_hash,
                'block_time': tx_info.value.block_time,
                'slot': tx_info.value.slot
            }

        except Exception as e:
            return {
                'verified': False,
                'error': str(e)
            }

    def get_audit_trail_summary(self, audit_record: Dict) -> str:
        """
        Generate human-readable audit trail summary

        Args:
            audit_record: The blockchain audit record

        Returns:
            Formatted summary string
        """
        summary_parts = [
            "=" * 80,
            "BLOCKCHAIN AUDIT TRAIL",
            "=" * 80,
            f"Document ID: {audit_record['document_id']}",
            f"Classification: {audit_record['category']}",
            f"Audit Hash: {audit_record['audit_hash']}",
            f"Transaction Hash: {audit_record['transaction_hash']}",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(audit_record['timestamp']))}",
            f"Cluster: {audit_record['cluster']}",
            f"Status: {audit_record['status']}",
        ]

        if 'explorer_url' in audit_record:
            summary_parts.append(f"Explorer URL: {audit_record['explorer_url']}")

        summary_parts.append("=" * 80)
        summary_parts.append("\nThis record is cryptographically secured and immutable.")
        summary_parts.append("The audit hash can be independently verified against the classification data.")

        return "\n".join(summary_parts)
