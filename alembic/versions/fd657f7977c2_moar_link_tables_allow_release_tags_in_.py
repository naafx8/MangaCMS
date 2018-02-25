"""Moar link tables, allow release tags in addition to file tags

Revision ID: fd657f7977c2
Revises: af01f97c978e
Create Date: 2018-02-23 22:28:19.719140

"""

# revision identifiers, used by Alembic.
revision = 'fd657f7977c2'
down_revision = 'af01f97c978e'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

import sqlalchemy_utils
import sqlalchemy_jsonfield

# Patch in knowledge of the citext type, so it reflects properly.
from sqlalchemy.dialects.postgresql.base import ischema_names
import citext
import queue
import datetime
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import TSVECTOR
ischema_names['citext'] = citext.CIText



def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('hentai_files_tags_link',
    sa.Column('releases_id', sa.Integer(), nullable=False),
    sa.Column('tags_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['releases_id'], ['release_files.id'], ),
    sa.ForeignKeyConstraint(['tags_id'], ['hentai_tags.id'], ),
    sa.PrimaryKeyConstraint('releases_id', 'tags_id')
    )
    op.create_table('manga_files_tags_link',
    sa.Column('releases_id', sa.Integer(), nullable=False),
    sa.Column('tags_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['releases_id'], ['release_files.id'], ),
    sa.ForeignKeyConstraint(['tags_id'], ['manga_tags.id'], ),
    sa.PrimaryKeyConstraint('releases_id', 'tags_id')
    )
    op.create_table('hentai_releases_tags_link',
    sa.Column('releases_id', sa.Integer(), nullable=False),
    sa.Column('tags_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['releases_id'], ['hentai_releases.id'], ),
    sa.ForeignKeyConstraint(['tags_id'], ['hentai_tags.id'], ),
    sa.PrimaryKeyConstraint('releases_id', 'tags_id')
    )
    op.create_table('manga_releases_tags_link',
    sa.Column('releases_id', sa.Integer(), nullable=False),
    sa.Column('tags_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['releases_id'], ['manga_releases.id'], ),
    sa.ForeignKeyConstraint(['tags_id'], ['manga_tags.id'], ),
    sa.PrimaryKeyConstraint('releases_id', 'tags_id')
    )
    op.drop_table('manga_tags_link')
    op.drop_table('hentai_tags_link')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('hentai_tags_link',
    sa.Column('releases_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('tags_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['releases_id'], ['release_files.id'], name='hentai_tags_link_releases_id_fkey'),
    sa.ForeignKeyConstraint(['tags_id'], ['hentai_tags.id'], name='hentai_tags_link_tags_id_fkey'),
    sa.PrimaryKeyConstraint('releases_id', 'tags_id', name='hentai_tags_link_pkey')
    )
    op.create_table('manga_tags_link',
    sa.Column('releases_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('tags_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['releases_id'], ['release_files.id'], name='manga_tags_link_releases_id_fkey'),
    sa.ForeignKeyConstraint(['tags_id'], ['manga_tags.id'], name='manga_tags_link_tags_id_fkey'),
    sa.PrimaryKeyConstraint('releases_id', 'tags_id', name='manga_tags_link_pkey')
    )
    op.drop_table('manga_releases_tags_link')
    op.drop_table('hentai_releases_tags_link')
    op.drop_table('manga_files_tags_link')
    op.drop_table('hentai_files_tags_link')
    # ### end Alembic commands ###