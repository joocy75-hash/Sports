import axios from 'axios';

// 프로덕션에서는 상대 경로 사용, 개발에서는 localhost
const API_BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? '/sports' : 'http://localhost:8000');

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
});

// 요청 인터셉터
apiClient.interceptors.request.use(
    (config) => {
        // 필요시 인증 토큰 추가
        // const token = localStorage.getItem('token');
        // if (token) {
        //   config.headers.Authorization = `Bearer ${token}`;
        // }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// 응답 인터셉터
apiClient.interceptors.response.use(
    (response) => {
        return response.data;
    },
    (error) => {
        console.error('API Error:', error);

        // 에러 메시지 가공
        if (error.response) {
            const { status, data } = error.response;

            switch (status) {
                case 400:
                    console.error('잘못된 요청:', data);
                    break;
                case 401:
                    console.error('인증 필요');
                    break;
                case 404:
                    console.error('리소스를 찾을 수 없음');
                    break;
                case 500:
                    console.error('서버 오류');
                    break;
                default:
                    console.error(`HTTP ${status} 오류`);
            }
        } else if (error.request) {
            console.error('서버 응답 없음 - 네트워크 오류');
        }

        return Promise.reject(error);
    }
);

export default apiClient;
