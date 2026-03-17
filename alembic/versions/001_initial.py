"""Initial models migration

Revision ID: 001_initial
Revises:
Create Date: 2026-03-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Create initial database schema"""
    # 1. Create ENUM types using safe SQL execution
    # This block ensures types exist before we define columns.
    conn = op.get_bind()
    
    enums = [
        ("roleenum", "('ADMIN', 'ARCHIVIST', 'INSPECTOR', 'VIEWER', 'SYSTEM')"),
        ("pastrareEnum", "('6_months', '1_year', '3_years', '5_years', '7_years', '10_years', 'permanent')"),
        ("documentstatusenum", "('uploaded', 'processing', 'classified', 'extracted', 'validated', 'archived', 'rejected')"),
        ("documenttypeenum", "('invoice', 'contract', 'report', 'correspondence', 'decision', 'protocol', 'other')"),
        ("auditactionenum", "('create', 'read', 'update', 'delete', 'download', 'upload', 'classify', 'extract', 'archive', 'restore', 'login', 'logout', 'permission_change')"),
        ("anomalytypeenum", "('fraud', 'anomaly')")
    ]

    for name, values in enums:
        # Note the semicolon after NULL
        conn.execute(sa.text(f"DO $$ BEGIN CREATE TYPE \"{name}\" AS ENUM {values}; EXCEPTION WHEN duplicate_object THEN NULL; END $$;"))

    # 2. Define Enum objects for table columns
    # We use postgresql.ENUM and explicitly set create_type=False
    roleenum = postgresql.ENUM('ADMIN', 'ARCHIVIST', 'INSPECTOR', 'VIEWER', 'SYSTEM', name='roleenum', create_type=False)
    pastrareenum = postgresql.ENUM('6_months', '1_year', '3_years', '5_years', '7_years', '10_years', 'permanent', name='pastrareEnum', create_type=False)
    documentstatusenum = postgresql.ENUM('uploaded', 'processing', 'classified', 'extracted', 'validated', 'archived', 'rejected', name='documentstatusenum', create_type=False)
    documenttypeenum = postgresql.ENUM('invoice', 'contract', 'report', 'correspondence', 'decision', 'protocol', 'other', name='documenttypeenum', create_type=False)
    auditactionenum = postgresql.ENUM('create', 'read', 'update', 'delete', 'download', 'upload', 'classify', 'extract', 'archive', 'restore', 'login', 'logout', 'permission_change', name='auditactionenum', create_type=False)
    anomalytypeenum = postgresql.ENUM('fraud', 'anomaly', name='anomalytypeenum', create_type=False)

    # users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', roleenum, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.literal(True)),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.literal(False)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])

    # nomenclator table
    op.create_table(
        'nomenclator',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('default_termen_pastrare', pastrareenum, nullable=False),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['nomenclator.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_nomenclator_id', 'nomenclator', ['id'])
    op.create_index('ix_nomenclator_code', 'nomenclator', ['code'])
    op.create_index('ix_nomenclator_parent_id', 'nomenclator', ['parent_id'])

    # dosare table
    op.create_table(
        'dosare',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dosar_number', sa.String(255), nullable=False),
        sa.Column('title', sa.String(511), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('nomenclator_id', sa.Integer(), nullable=False),
        sa.Column('termen_pastrare', pastrareenum, nullable=False),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['nomenclator_id'], ['nomenclator.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dosar_number'),
    )
    op.create_index('ix_dosare_id', 'dosare', ['id'])
    op.create_index('ix_dosare_dosar_number', 'dosare', ['dosar_number'])

    # documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_number', sa.String(255), nullable=False),
        sa.Column('document_type', documenttypeenum, nullable=False),
        sa.Column('title', sa.String(511), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, server_default='RON'),
        sa.Column('file_path', sa.String(511), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('status', documentstatusenum, nullable=False),
        sa.Column('fraud_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('dosar_id', sa.Integer(), nullable=True),
        sa.Column('nomenclator_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('document_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['dosar_id'], ['dosare.id'], ),
        sa.ForeignKeyConstraint(['nomenclator_id'], ['nomenclator.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_number'),
    )
    op.create_index('ix_documents_id', 'documents', ['id'])
    op.create_index('ix_documents_document_number', 'documents', ['document_number'])
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_dosar_id', 'documents', ['dosar_id'])

    # document_pages table
    op.create_table(
        'document_pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('image_path', sa.String(511), nullable=False),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_pages_id', 'document_pages', ['id'])
    op.create_index('ix_document_pages_document_id', 'document_pages', ['document_id'])

    # extracted_data table
    op.create_table(
        'extracted_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(255), nullable=False),
        sa.Column('field_value', sa.Text(), nullable=False),
        sa.Column('extraction_confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_extracted_data_id', 'extracted_data', ['id'])
    op.create_index('ix_extracted_data_document_id', 'extracted_data', ['document_id'])

    # audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', auditactionenum, nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('changes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_resource_id', 'audit_logs', ['resource_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    # fraud_alerts table
    op.create_table(
        'fraud_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('anomaly_type', anomalytypeenum, nullable=False),
        sa.Column('severity', sa.String(50), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_reviewed', sa.Boolean(), nullable=False, server_default=sa.literal(False)),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fraud_alerts_id', 'fraud_alerts', ['id'])
    op.create_index('ix_fraud_alerts_document_id', 'fraud_alerts', ['document_id'])


def downgrade() -> None:
    """Drop all tables"""
    op.drop_table('fraud_alerts')
    op.drop_table('audit_logs')
    op.drop_table('extracted_data')
    op.drop_table('document_pages')
    op.drop_table('documents')
    op.drop_table('dosare')
    op.drop_table('nomenclator')
    op.drop_table('users')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS roleenum;")
    op.execute("DROP TYPE IF EXISTS pastrareEnum;")
    op.execute("DROP TYPE IF EXISTS documentstatusenum;")
    op.execute("DROP TYPE IF EXISTS documenttypeenum;")
    op.execute("DROP TYPE IF EXISTS auditactionenum;")
    op.execute("DROP TYPE IF EXISTS anomalytypeenum;")