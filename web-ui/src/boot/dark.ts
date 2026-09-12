import { Dark } from 'quasar';

export default () => {
  const saved = localStorage.getItem('nas.dark');
  Dark.set(saved === null ? true : saved === '1');
};