import { useQuasar } from 'quasar';

export default (() => {
  const $q = useQuasar();
  const saved = localStorage.getItem('nas.dark');
  $q.dark.set(saved === null ? true : saved === '1');
});