/** User types — mirrors backend schemas/users.py. */

export interface User {
  id: number;
  username: string;
  display_name: string;
  grade: number;
  track: string;
  timezone: string;
}
