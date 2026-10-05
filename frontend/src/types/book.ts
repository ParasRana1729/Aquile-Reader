export interface BookWithProgress {
  id: string;
  title: string;
  author: string | null;
  filePath: string;
  format: 'epub' | 'pdf' | 'cbz' | 'cbr' | string;
  coverImage: string | null;
  pageCount: number;
  chapterCount: number;
  fileSize: number;
  isFavorite: boolean;
  addedDate: string;
  lastReadDate: string | null;
  percentage: number;
  position: string | null;
}

export type ViewMode = 'grid' | 'shelf' | 'list';
export type SortOption = 'recent' | 'title' | 'author';
export type CollectionFilter = 'all' | 'favorites' | 'epub' | 'pdf' | 'cbz';
