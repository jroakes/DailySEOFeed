# daily_seo_feed.py

"""Feed ranking algorithm for SEO content."""
from datetime import timedelta, timezone, datetime
from typing import List, Dict, Any, Tuple, Optional
from server.database import Post, get_utc_now
from server.logger import logger
from server.authors import author_manager
from server import config
import pandas as pd
import numpy as np
from time import time

# Feed identifier
URI = config.DAILY_SEO_FEED_URI


class PostRanker:
    """Handles post ranking and scoring logic."""
    
    def __init__(self, config: Any):
        """Initialize the post ranker with configuration."""
        self.config = config
        self.rank_config = config.rank_config
        self.cache_duration = 300  # 5 minutes
        self._last_cache_reset = time()
        self._cached_df = None


    def calculate_velocity(self, timestamps: List[str], now: datetime, window_hours: int) -> float:
        """Calculate weighted velocity score."""
        recent_count = 0
        very_recent_count = 0
        
        for ts in timestamps:
            try:
                interaction_time = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                age_hours = (now - interaction_time).total_seconds() / 3600
                
                if age_hours <= window_hours:
                    recent_count += 1
                    if age_hours <= window_hours/2:  # Extra weight for very recent
                        very_recent_count += 1
            except ValueError:
                continue
                
        return recent_count + (very_recent_count * 0.5)


    def get_scored_posts(self) -> pd.DataFrame:
        """Get all scored posts from the database.
        
        Returns:
            DataFrame with scored posts
        """
        cutoff_time = get_utc_now() - timedelta(hours=self.config.POST_LIFETIME_HOURS)
        posts = list(Post.select().where(Post.indexed_at >= cutoff_time))
        
        df = self.build_base_df(posts, get_utc_now())

        if len(df) == 0:
            return pd.DataFrame()
            
        df = self.normalize_scores(df)
        df = self.calculate_final_scores(df)
        
        return df


    def build_base_df(self, posts: List[Post], now: datetime) -> pd.DataFrame:
        """Create initial dataframe with post data."""
        data = []
        for post in posts:
            try:
                engaged_authors = post.engaged_authors or []
                
                # Calculate basic engagement
                engagement = (
                    post.likes_count * self.rank_config['WEIGHT_LIKES'] +
                    post.reposts_count * self.rank_config['WEIGHT_REPOSTS'] +
                    post.replies_count * self.rank_config['WEIGHT_COMMENTS']
                )
                
                # Calculate velocity with new method
                velocity = self.calculate_velocity(
                    post.interaction_timestamps or [],
                    now,
                    self.rank_config['RECENT_INTERACTION_WINDOW']
                )
                
                data.append({
                    'post_id': post.id,
                    'uri': post.uri,
                    'author_handle': post.author_handle,
                    'text': post.text,
                    'engagement_score': float(engagement),
                    'engaged_authors_count': len(engaged_authors),
                    'velocity': float(velocity),
                    'indexed_at': post.indexed_at.replace(tzinfo=timezone.utc)
                })
                
            except Exception as e:
                logger.error(f"Error processing post {post.uri}: {e}")
                continue
                
        df = pd.DataFrame(data)
        if len(df) == 0:
            return pd.DataFrame(columns=[
                'post_id', 'uri', 'author_handle', 'text', 
                'engagement_score', 'engaged_authors_count', 
                'velocity', 'indexed_at'
            ])
        return df


    def normalize_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize all scoring components to 0-1 range."""
        if len(df) == 0:
            return df
            
        # Normalize engagement scores
        max_engagement = df['engagement_score'].max()
        df['engagement_norm'] = df['engagement_score'] / max_engagement if max_engagement > 0 else 0
        
        # Normalize velocity
        max_velocity = df['velocity'].max()
        df['velocity_norm'] = df['velocity'] / max_velocity if max_velocity > 0 else 0
        
        # Calculate quorum score
        total_authors = len(author_manager.author_dids)
        df['quorum_score'] = df['engaged_authors_count'] / total_authors if total_authors > 0 else 0
        
        # Calculate time decay
        df['age_hours'] = (pd.Timestamp(get_utc_now()) - df['indexed_at']).dt.total_seconds() / 3600
        df['time_decay'] = 1 / (1 + np.exp((df['age_hours'] - self.rank_config['DECAY_MIDPOINT']) / 
                                          self.rank_config['DECAY_RATE']))
        
        return df


    def calculate_final_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate weighted final scores."""
        if len(df) == 0:
            return df
            
        weights = self.rank_config['SCORE_WEIGHTS']
        
        df['final_score'] = (
            df['engagement_norm'] * weights['BASE_ENGAGEMENT'] +
            df['quorum_score'] * weights['QUORUM'] +
            df['velocity_norm'] * weights['VELOCITY']
        ) * df['time_decay']
        
        return df.sort_values('final_score', ascending=False)


    def _handle_cursor(self, df: pd.DataFrame, cursor: str) -> pd.DataFrame:
        """Filter dataframe based on cursor position."""
        if not cursor or cursor == self.config.CURSOR_EOF:
            return df
            
        try:
            score, post_id = cursor.split("::")
            return df[
                (df['final_score'] < float(score)) | 
                ((df['final_score'] == float(score)) & (df['post_id'] < int(post_id)))
            ]
        except (ValueError, TypeError):
            logger.error(f"Invalid cursor: {cursor}")
            return df


    def _get_next_cursor(self, df: pd.DataFrame, page_df: pd.DataFrame, limit: int) -> str:
        """Generate the next cursor based on the current page."""
        if len(page_df) == 0 or len(df) <= limit:
            return self.config.CURSOR_EOF
            
        last_row = page_df.iloc[-1]
        return f"{last_row['final_score']:.6f}::{last_row['post_id']}"


    def get_posts(self, cursor: Optional[str], limit: int) -> Tuple[List[Dict[str, Any]], str]:
        """Get paginated, ranked posts."""
        try:
            limit = min(max(1, limit), 100)  # Ensure limit is between 1 and 100
            
            # Get scored posts
            df = self.get_scored_posts()
            
            if len(df) == 0:
                return [], self.config.CURSOR_EOF
            
            # Apply minimum score filter and cursor pagination
            df = df[df['final_score'] >= self.rank_config['MIN_ENGAGEMENT_SCORE']]
            df = self._handle_cursor(df, cursor)
            
            # Get page
            page_df = df.head(limit)
            
            if len(page_df) == 0:
                return [], self.config.CURSOR_EOF
            
            # Generate next cursor
            next_cursor = self._get_next_cursor(df, page_df, limit)
            
            # Prepare response
            feed = [
                {
                    'uri': row['uri'],
                    'author_handle': row['author_handle'],
                    'text': row['text'],
                    'engagement_score': row['final_score'],
                    'indexed_at': row['indexed_at']
                }
                for _, row in page_df.iterrows()
            ]
            
            return feed, next_cursor
            
        except Exception as e:
            logger.error(f"Error in get_posts: {e}", exc_info=True)
            return [], self.config.CURSOR_EOF



def handler(cursor: Optional[str], limit: int) -> Dict[str, Any]:
    """API handler function for feed requests."""
    ranker = PostRanker(config)
    feed, next_cursor = ranker.get_posts(cursor, limit)
    feed = [{"uri": post["uri"]} for post in feed]  # Format for API response
    return {
        "cursor": next_cursor,
        "feed": feed
    }